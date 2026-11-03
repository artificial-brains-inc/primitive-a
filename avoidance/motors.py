"""Fixed SDK decoding of each native output frame into wheel velocities."""
import math
from .sensors import OUTPUTS
from .contracts import OUTPUT_SIZES


def validate_channels(event):
    step = event.get("step")
    channels = (event.get("actuation") or {}).get("channels")
    if type(step) is not int or not isinstance(channels, dict):
        raise ValueError("Expected a native step and actuation.channels.")
    if set(channels) != set(OUTPUT_SIZES):
        raise ValueError("Installed brain has different outputs from this project.")
    for name in OUTPUT_SIZES:
        value = channels[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value not in (0, 1):
            raise ValueError(f"Expected a single-neuron count for {name}.")
    return channels


class MotorCommands:
    def __init__(self, speed):
        from ab import ActuationChannelDecoder
        if not math.isfinite(speed) or not 0 < speed <= 8:
            raise ValueError("Wheel speed must be between 0 and 8 rad/s, excluding zero.")
        self.decoder = ActuationChannelDecoder({
            name: {"motor": name, "gain": speed} for name in OUTPUTS})
        self.speed = speed
        self.speeds = dict.fromkeys(OUTPUTS, 0.0)
        self.last_step = None

    def apply(self, event):
        validate_channels(event)
        if self.last_step is not None and event["step"] <= self.last_step:
            raise ValueError("An output frame cannot be applied twice.")
        decoded = self.decoder.decode(event, {})["deltas"]
        # These are absolute velocities for this frame, not accumulated changes.
        self.speeds = {name: min(self.speed, max(0.0, decoded.get(name, 0.0))) for name in OUTPUTS}
        self.last_step = event["step"]
        return dict(self.speeds)
