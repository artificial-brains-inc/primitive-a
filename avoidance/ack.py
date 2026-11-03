"""One atomic observation, one neural ACK, then immediate motor execution."""
from __future__ import annotations
import math
import threading
import time

from .contracts import ACK_INPUT, ACK_OUTPUT, INPUT_SIZES
from .motors import validate_channels


class AcknowledgedObservations:
    """Synchronize Webots with the neural engine's acknowledgement output.

    An HTTP queue receipt and unrelated wheel activity cannot acknowledge a
    snapshot. Never retry a snapshot whose processing status is unknown.
    The Webots thread waits here; physics advances only after this returns.
    """
    def __init__(self, publish, events, *, timeout_seconds=30,
                 record=lambda event: None, clock=time.monotonic):
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("ACK timeout must be positive and finite.")
        self.publish = publish
        self.events = events
        self.timeout_seconds = timeout_seconds
        self.record = record
        self.clock = clock
        self.sequence = 0
        self.last_ack_step = -1
        self.failed = False
        self.phase = "idle"
        self.transaction = threading.Lock()

    def _record(self, kind, **fields):
        self.record(dict(kind=kind, sequence=self.sequence,
                         monotonic_ns=time.monotonic_ns(), **fields))

    def _next(self, deadline):
        event = self.events.wait_one(deadline)
        validate_channels(event)
        return event

    def _wait_clear(self):
        self.phase = "ACK clear"
        self._record("ack_clear_started", after_step=self.last_ack_step)
        deadline = self.clock() + self.timeout_seconds
        while True:
            event = self._next(deadline)
            step = event["step"]
            if step <= self.last_ack_step:
                continue
            # Consume buffered frames so an old zero cannot hide a newer high
            # ACK. A current clear frame is enough; no fixed quiet-frame count.
            if event["actuation"]["channels"][ACK_OUTPUT] == 0 and self.events.stats()["queued_frames"] == 0:
                self._record("ack_clear", step=step)
                return step

    def decide(self, capture):
        """Capture after ACK clears; return the first fresh ACK frame immediately."""
        if not self.transaction.acquire(blocking=False):
            raise RuntimeError("An observation is already awaiting its neural ACK.")
        try:
            if self.failed:
                raise RuntimeError("The previous observation failed; stop and restart the session before sending again.")
            return self._decide(capture)
        except Exception as exc:
            self.failed = True
            self._record("observation_failed", phase=self.phase, error_type=type(exc).__name__)
            raise
        finally:
            self.transaction.release()

    def _decide(self, capture):
        clear_step = self._wait_clear()
        frame, observation = capture()
        if set(frame) != set(INPUT_SIZES) - {ACK_INPUT}:
            raise ValueError("Capture must contain camera and both proximity measurements only.")
        payload = {name: list(values) for name, values in frame.items()}
        payload[ACK_INPUT] = [1.0]
        for name, values in payload.items():
            if len(values) != INPUT_SIZES[name]:
                raise ValueError(f"Wrong observation width for {name}.")
        after_step = self.events.stats()["last_received_step"]
        after_step = clear_step if after_step is None else after_step
        self.sequence += 1
        self.phase = "sensor submission"
        self._record("sensor_send_started", after_step=after_step,
                     input_activity={name: sum(values) for name, values in payload.items()})
        reply = self.publish(payload, mode="vector_f32")
        if not isinstance(reply, dict) or reply.get("ok") is not True or reply.get("queued_for_hardware") is not True or reply.get("atomic_frame") is not True:
            raise RuntimeError("The SDK did not confirm atomic queue acceptance; do not retry this observation.")
        self._record("sensor_queue_accepted")
        self.phase = "neural ACK"
        deadline = self.clock() + self.timeout_seconds
        while True:
            event = self._next(deadline)
            if event["step"] > after_step and event["actuation"]["channels"][ACK_OUTPUT] > 0:
                ack_step = event["step"]
                break
        self._record("neural_ack", step=ack_step)

        self.last_ack_step = ack_step
        result = {"sequence": self.sequence, "clear_step": clear_step,
                  "ack_step": ack_step, "decision_step": ack_step,
                  "observation": observation, "decision_frame": event}
        self._record("decision_complete", ack_step=ack_step, step=ack_step)
        self.phase = "idle"
        return result
