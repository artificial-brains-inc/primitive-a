import contextlib
import io
import json
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from avoidance import bridge
from avoidance.contracts import ACK_INPUT, ACK_OUTPUT
from avoidance.transport import EventBuffer


def event(step, ack=0, left=1, right=1):
    return {"step": step, "actuation": {"channels": {
        "WHEEL_LEFT": left, "WHEEL_RIGHT": right, ACK_OUTPUT: ack}}}


class BridgeTests(unittest.TestCase):
    def exercise_bridge(self, frames, decisions, error=False, step_ms=16):
        trace = []
        cursor = [0]
        frames = iter(frames)
        main_thread = threading.get_ident()

        class ArrivingEvents(EventBuffer):
            def wait_one(self, deadline):
                try:
                    item = next(frames)
                except StopIteration:
                    raise TimeoutError("No more native frames") from None
                cursor[0] = item["step"]
                trace.append(("neural", cursor[0]))
                self.on_output(item)
                return super().wait_one(deadline)

        class Motor:
            def __init__(self, name):
                self.name = name
            def setPosition(self, value):
                pass
            def setVelocity(self, value):
                check_main_thread()
                trace.append(("motor", self.name, value, cursor[0]))

        def check_main_thread():
            self.assertEqual(threading.get_ident(), main_thread)

        motors = {name: Motor(name) for name in ("left wheel motor", "right wheel motor")}
        robot = Mock()
        robot.getDevice.side_effect = motors.__getitem__
        physics_calls = []

        def physics_step(step):
            check_main_thread()
            trace.append(("physics", step, cursor[0]))
            if step == 0:
                return -1
            physics_calls.append(cursor[0])
            # First step initializes sensors with zero wheel speeds.
            return -1 if len(physics_calls) > decisions else 0

        robot.step.side_effect = physics_step
        robot.getTime.side_effect = lambda: len(physics_calls) * step_ms / 1000
        sensors = Mock()

        def capture(config):
            check_main_thread()
            trace.append(("capture", cursor[0]))
            return {"CAMERA": [0.5] * 64, "PROX_LEFT": [0.0] * 16,
                    "PROX_RIGHT": [1.0] * 16}, {
                        "proximity_left": 0, "proximity_right": 1000, "camera_mean": 0.5}

        sensors.capture.side_effect = capture
        session = Mock()

        def publish(payload, **kwargs):
            check_main_thread()
            trace.append(("publish", cursor[0]))
            self.assertEqual(payload[ACK_INPUT], [1.0])
            return {"ok": True, "queued_for_hardware": True, "atomic_frame": True}

        session.publish_sensor_frame.side_effect = publish
        client = Mock()
        client.start_from_env.return_value = session
        config = {"physics_step_ms": step_ms, "output_timeout_seconds": 5,
                  "ack_timeout_seconds": 30,
                  "wheel_speed_rad_s": 3, "proximity_full_scale": 1000}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.dict("sys.modules", {"controller": types.SimpleNamespace(Robot=lambda: robot)}))
                stack.enter_context(patch("ab.ABClient.from_env", return_value=client))
                stack.enter_context(patch("avoidance.application.verify_installed"))
                stack.enter_context(patch.object(bridge, "ROOT", root))
                stack.enter_context(patch.object(bridge.os, "chdir"))
                stack.enter_context(patch.dict("os.environ", {}))
                stack.enter_context(patch.object(bridge, "Sensors", return_value=sensors))
                stack.enter_context(patch.object(bridge, "EventBuffer", ArrivingEvents))
                stack.enter_context(patch.object(bridge, "load_config", return_value=config))
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                bridge.main()
            state = json.loads((root / "logs/run_state.json").read_text())
            self.assertTrue(state["neural_stop_confirmed"])
            self.assertEqual(state["state"], "ERROR" if error else "STOPPED")
            records = [json.loads(line) for path in (root / "logs").glob("run-*.jsonl")
                       for line in path.read_text().splitlines()]
            for record in records[1:]:
                self.assertEqual(record["ack_step"], record["decision_step"])
        session.stop.assert_called_once()
        client.close.assert_called_once()
        return trace

    def test_each_ack_executes_once_before_reading_another_neural_frame(self):
        trace = self.exercise_bridge([
            event(1), event(2), event(3, ack=1, left=0),
            event(4, ack=1), event(5), event(6, ack=1, right=0)], decisions=2)
        self.assertEqual([item for item in trace if item[0] == "physics"],
                         [("physics", 16, 0), ("physics", 16, 3), ("physics", 16, 6), ("physics", 0, 6)])
        self.assertEqual([item for item in trace if item[0] == "publish"], [("publish", 1), ("publish", 5)])
        self.assertEqual([item for item in trace if item[0] == "motor" and item[2] > 0],
                         [("motor", "right wheel motor", 3.0, 3), ("motor", "left wheel motor", 3.0, 6)])
        self.assertLess(trace.index(("physics", 16, 3)), trace.index(("neural", 4)))

    def test_missing_ack_or_stream_gap_does_not_advance_body(self):
        for frames in ([event(1), event(2), event(3)], [event(1), event(3, ack=1)]):
            with self.subTest(frames=frames):
                trace = self.exercise_bridge(frames, decisions=1, error=True)
                self.assertEqual([item for item in trace if item[0] == "physics" and item[1] == 16],
                                 [("physics", 16, 0)])
                self.assertFalse(any(item[0] == "motor" and item[2] > 0 for item in trace))

    def test_longer_movement_still_executes_once_per_ack(self):
        for step_ms in (32, 64, 128):
            with self.subTest(step_ms=step_ms):
                trace = self.exercise_bridge([event(1), event(2), event(3, ack=1)],
                                             decisions=1, step_ms=step_ms)
                self.assertEqual([item for item in trace if item[0] == "physics"],
                                 [("physics", step_ms, 0), ("physics", step_ms, 3), ("physics", 0, 3)])
                self.assertEqual([item for item in trace if item[0] == "publish"], [("publish", 1)])


if __name__ == "__main__":
    unittest.main()
