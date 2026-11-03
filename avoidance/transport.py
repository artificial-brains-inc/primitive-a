from __future__ import annotations

from collections import deque
import math
import threading
import time



class StopRequested(Exception):
    pass


class EventBuffer:
    """Thread-safe delivery of real Prima-Lux output frames, without inference."""
    def __init__(self, stop_requested=lambda: False, *, timeout_seconds=None, clock=time.monotonic):
        self.condition = threading.Condition()
        self.events = deque()
        self.sequence = 0
        self.last_step = None
        self.failure = None
        self.stop_requested = stop_requested
        self.remote_stop = False
        if timeout_seconds is not None and (not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
            raise ValueError("Output timeout must be positive and finite.")
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self.last_received = clock()

    def on_control(self, event):
        if event.get("command") == "stop":
            with self.condition:
                self.remote_stop = True
                self.condition.notify_all()

    def on_output(self, event):
        try:
            step = event.get("step")
            channels = (event.get("actuation") or {}).get("channels")
            if type(step) is not int or not isinstance(channels, dict):
                raise ValueError("Expected native step and actuation.channels; no alternate outputs are fabricated.")
            for name, value in channels.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid actuation count for {name}.")
            with self.condition:
                if self.last_step is not None and step < self.last_step:
                    raise ValueError("Prima-Lux output steps went backwards; restart the session.")
                if step == self.last_step:
                    return
                if self.last_step is not None and step != self.last_step + 1:
                    raise ValueError(f"Missing Prima-Lux motor frames: {self.last_step} -> {step}. Restart the session.")
                if len(self.events) >= 4096:
                    raise RuntimeError("Output buffer overflow; stopping rather than losing motor events.")
                self.last_step = step
                self.sequence += 1
                self.last_received = self.clock()
                # Host receipt timestamp, not an invented device timestamp.
                stamped = dict(event, bridge_received_monotonic_ns=time.monotonic_ns())
                self.events.append((self.sequence, stamped))
                self.condition.notify_all()
        except Exception as exc:
            with self.condition:
                self.failure = str(exc)
                self.condition.notify_all()

    def check_health(self):
        """Check Stop and stream health without consuming a neural frame."""
        with self.condition:
            if self.remote_stop or self.stop_requested():
                raise StopRequested("Stop requested.")
            if self.failure:
                raise RuntimeError(self.failure)
            if self.timeout_seconds is not None and self.clock() - self.last_received >= self.timeout_seconds:
                raise RuntimeError("Prima-Lux output stream timed out; stopping motors and saving neural state.")

    def take_one(self):
        """Deliver at most one frame to the ACK/readout exchange; retain the rest."""
        with self.condition:
            self.check_health()
            return [self.events.popleft()] if self.events else []

    def stats(self):
        with self.condition:
            return {"queued_frames": len(self.events), "last_received_step": self.last_step,
                    "seconds_since_last_native_frame": self.clock() - self.last_received}

    def wait_one(self, deadline):
        """Wait for a real frame while checking Stop, stream health and deadline."""
        with self.condition:
            while True:
                if self.clock() >= deadline:
                    raise TimeoutError("Neural acknowledgement/decision deadline expired.")
                received = self.take_one()
                if received:
                    return received[0][1]
                self.condition.wait(timeout=min(0.05, max(0, deadline - self.clock())))
