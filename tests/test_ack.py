from collections import deque
import threading
import time
import unittest

from design_brain import create_brain
from avoidance.ack import AcknowledgedObservations
from avoidance.contracts import ACK_INPUT, ACK_OUTPUT
from avoidance.motors import MotorCommands
from avoidance.transport import EventBuffer, StopRequested


def event(step, ack=0, left=1, right=1):
    return {"step": step, "actuation": {"channels": {
        "WHEEL_LEFT": left, "WHEEL_RIGHT": right, ACK_OUTPUT: ack}}}


def capture():
    return {"CAMERA": [0.5] * 64, "PROX_LEFT": [0.0] * 16,
            "PROX_RIGHT": [1.0] * 16}, {"sample": "current"}


QUEUE_ACCEPTED = {"ok": True, "queued_for_hardware": True, "atomic_frame": True}


class ArrivingFrames:
    """Scripted arrivals, delivered only as the caller waits for each frame."""
    def __init__(self, frames, cursor=None):
        self.frames = deque(frames)
        self.cursor = cursor

    def stats(self):
        return {"last_received_step": self.cursor, "queued_frames": 0}

    def wait_one(self, deadline):
        if not self.frames:
            raise TimeoutError("No further neural frame arrived")
        item = self.frames.popleft()
        if isinstance(item, Exception):
            raise item
        self.cursor = max(self.cursor if self.cursor is not None else -1, item["step"])
        return item


class ACKTests(unittest.TestCase):
    def test_ack_component_is_isolated_and_clears_its_output(self):
        design = create_brain().to_dict()
        ack_names = {n["name"] for n in design["nodes"] if n["name"].startswith("TRANSPORT_ACK")}
        self.assertEqual(len(design["nodes"]), 21)
        self.assertEqual(len(design["connections"]), 25)
        self.assertEqual(ack_names, {ACK_INPUT, ACK_OUTPUT, "TRANSPORT_ACK_RELAY", "TRANSPORT_ACK_CLEAR"})
        ack_edges = []
        for edge in design["connections"]:
            if edge["from"] in ack_names or edge["to"] in ack_names:
                self.assertIn(edge["from"], ack_names)
                self.assertIn(edge["to"], ack_names)
                ack_edges.append(edge)
        self.assertEqual({(e["from"], e["to"], e["type"]) for e in ack_edges}, {
            (ACK_INPUT, "TRANSPORT_ACK_RELAY", "exc"),
            ("TRANSPORT_ACK_RELAY", ACK_OUTPUT, "exc"),
            (ACK_OUTPUT, "TRANSPORT_ACK_CLEAR", "exc"),
            ("TRANSPORT_ACK_CLEAR", ACK_OUTPUT, "inh"),
            ("TRANSPORT_ACK_CLEAR", "TRANSPORT_ACK_CLEAR", "inh"),
        })
        self.assertEqual(next(e for e in ack_edges if e["from"] == e["to"])["role"], "feedback")

    def test_atomic_snapshot_executes_ack_frame_without_reading_later_frames(self):
        frames = ArrivingFrames([event(1), event(2, ack=1, left=0), event(3)])
        calls = []
        def publish(payload, **kwargs):
            calls.append((payload, kwargs, frames.cursor))
            return QUEUE_ACCEPTED
        def measured_capture():
            self.assertEqual(frames.cursor, 1)
            return capture()
        result = AcknowledgedObservations(publish, frames).decide(measured_capture)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][ACK_INPUT], [1.0])
        self.assertEqual(calls[0][0]["CAMERA"], [0.5] * 64)
        self.assertEqual(calls[0][1], {"mode": "vector_f32"})
        self.assertEqual(result["ack_step"], 2)
        self.assertEqual(result["decision_step"], 2)
        self.assertEqual(frames.cursor, 2)
        self.assertEqual([item["step"] for item in frames.frames], [3])
        self.assertEqual(MotorCommands(3).apply(result["decision_frame"]),
                         {"WHEEL_LEFT": 0.0, "WHEEL_RIGHT": 3.0})

    def test_wheel_activity_and_http_receipt_cannot_substitute_for_ack(self):
        frames = ArrivingFrames([event(i, left=i % 2) for i in range(1, 30)])
        calls = []
        def publish(payload, **kwargs):
            calls.append(payload)
            return QUEUE_ACCEPTED
        exchange = AcknowledgedObservations(publish, frames)
        with self.assertRaises(TimeoutError):
            exchange.decide(capture)
        self.assertEqual(exchange.phase, "neural ACK")
        self.assertEqual(len(calls), 1)
        with self.assertRaisesRegex(RuntimeError, "previous observation failed"):
            exchange.decide(capture)
        self.assertEqual(len(calls), 1)

    def test_stale_ack_does_not_acknowledge_new_observation(self):
        frames = ArrivingFrames([event(101), event(102, ack=1), event(103), event(104, ack=1)])
        def measured_capture():
            # A frame received before submission cannot acknowledge it.
            frames.cursor = 102
            return capture()
        result = AcknowledgedObservations(lambda *a, **k: QUEUE_ACCEPTED, frames).decide(measured_capture)
        self.assertEqual(result["ack_step"], 104)
        self.assertEqual(result["decision_step"], 104)

    def test_ack_must_be_clear_before_capture_or_submission(self):
        frames = ArrivingFrames([event(i, ack=1) for i in range(1, 10)])
        calls = []
        exchange = AcknowledgedObservations(lambda *a, **k: calls.append("publish"), frames)
        with self.assertRaises(TimeoutError):
            exchange.decide(lambda: calls.append("capture"))
        self.assertEqual(calls, [])

    def test_stuck_ack_prevents_next_observation_after_first_execution(self):
        frames = ArrivingFrames([event(1), event(2, ack=1), event(3, ack=1), event(4, ack=1)])
        calls = []
        def publish(payload, **kwargs):
            calls.append(payload)
            return QUEUE_ACCEPTED
        exchange = AcknowledgedObservations(publish, frames)
        self.assertEqual(exchange.decide(capture)["decision_step"], 2)
        with self.assertRaises(TimeoutError):
            exchange.decide(capture)
        self.assertEqual(exchange.phase, "ACK clear")
        self.assertEqual(len(calls), 1)

    def test_next_observation_starts_as_soon_as_ack_clears(self):
        frames = ArrivingFrames([event(1), event(2, ack=1), event(3, ack=1),
                                event(4), event(5, ack=1)])
        calls = []
        def publish(payload, **kwargs):
            calls.append(frames.cursor)
            return QUEUE_ACCEPTED
        exchange = AcknowledgedObservations(publish, frames)
        self.assertEqual(exchange.decide(capture)["decision_step"], 2)
        self.assertEqual(exchange.decide(capture)["decision_step"], 5)
        self.assertEqual(calls, [1, 4])

    def test_buffered_old_clear_frame_does_not_hide_current_high_ack(self):
        events = EventBuffer()
        events.on_output(event(1))
        events.on_output(event(2, ack=1))
        calls = []
        exchange = AcknowledgedObservations(lambda *a, **k: calls.append("publish"),
                                           events, timeout_seconds=.02)
        with self.assertRaises(TimeoutError):
            exchange.decide(lambda: calls.append("capture"))
        self.assertEqual(calls, [])

    def test_rejected_queue_receipt_and_concurrent_observation_are_not_retried(self):
        frames = ArrivingFrames([event(1)])
        calls = []
        exchange = None
        def publish(payload, **kwargs):
            calls.append(payload)
            with self.assertRaisesRegex(RuntimeError, "already awaiting"):
                exchange.decide(capture)
            return {"ok": False}
        exchange = AcknowledgedObservations(publish, frames)
        with self.assertRaisesRegex(RuntimeError, "queue acceptance"):
            exchange.decide(capture)
        self.assertEqual(len(calls), 1)

    def test_missing_ack_channel_is_not_silent_zero(self):
        first = event(1)
        del first["actuation"]["channels"][ACK_OUTPUT]
        with self.assertRaisesRegex(ValueError, "different outputs"):
            AcknowledgedObservations(lambda *a, **k: QUEUE_ACCEPTED, ArrivingFrames([first])).decide(capture)

    def test_event_buffer_handles_ack_arriving_during_http_submission(self):
        events = EventBuffer(timeout_seconds=2)
        ready = threading.Event()
        def feed_quiet():
            if ready.wait(2):
                for step in range(1, 4):
                    events.on_output(event(step))
        feeder = threading.Thread(target=feed_quiet)
        feeder.start()
        def publish(payload, **kwargs):
            events.on_output(event(4, ack=1))
            for step in range(5, 15):
                events.on_output(event(step))
            return QUEUE_ACCEPTED
        exchange = AcknowledgedObservations(
            publish, events, timeout_seconds=2,
            record=lambda record: ready.set() if record["kind"] == "ack_clear_started" else None)
        try:
            result = exchange.decide(capture)
            self.assertEqual(result["ack_step"], 4)
            self.assertEqual(result["decision_step"], 4)
            self.assertEqual(events.stats()["queued_frames"], 10)
        finally:
            feeder.join(timeout=2)
        self.assertFalse(feeder.is_alive())

    def test_remote_stop_interrupts_blocked_wait(self):
        events = EventBuffer()
        events.on_control({"command": "stop"})
        with self.assertRaises(StopRequested):
            events.wait_one(time.monotonic() + 1)

    def test_ack_never_maps_to_a_motor(self):
        self.assertEqual(MotorCommands(3).apply(event(1, ack=1, left=0, right=0)),
                         {"WHEEL_LEFT": 0.0, "WHEEL_RIGHT": 0.0})


if __name__ == "__main__":
    unittest.main()
