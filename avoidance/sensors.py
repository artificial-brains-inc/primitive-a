"""Measurements and fixed encodings; action selection belongs to the brain."""
import json
import math
from pathlib import Path
from .contracts import WHEEL_OUTPUTS as OUTPUTS

ROOT = Path(__file__).resolve().parents[1]
WORLD_BASIC_STEP_MS = 16


def load_config():
    config = json.loads((ROOT / "config.json").read_text())
    step = config.get("physics_step_ms")
    if type(step) is not int or step <= 0 or step % WORLD_BASIC_STEP_MS:
        raise ValueError("physics_step_ms must be a positive integer multiple of 16 ms (for example 16, 32 or 64).")
    for key in ("proximity_full_scale", "wheel_speed_rad_s", "output_timeout_seconds", "ack_timeout_seconds"):
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be positive and finite.")
    if config["wheel_speed_rad_s"] > 8:
        raise ValueError("The included wheels have an 8 rad/s physical maximum.")
    return config


def proximity_vector(raw, full_scale, width=16):
    if not math.isfinite(raw) or not math.isfinite(full_scale) or full_scale <= 0:
        raise ValueError("Invalid proximity measurement or full scale.")
    level = max(0.0, min(1.0, raw / full_scale))
    active = max(0, min(width, int(round(level * width))))
    return [1.0] * active + [0.0] * (width - active)


class Sensors:
    def __init__(self, robot, step):
        self.camera = robot.getDevice("camera")
        self.left = robot.getDevice("proximity_left")
        self.right = robot.getDevice("proximity_right")
        for sensor in (self.camera, self.left, self.right):
            if sensor is None:
                raise RuntimeError("The world is missing a required sensor.")
            sensor.enable(step)

    def capture(self, config):
        from controller import Camera
        image = self.camera.getImage()
        if image is None:
            raise RuntimeError("Camera frame is not available yet.")
        width, height = self.camera.getWidth(), self.camera.getHeight()
        pixels = []
        for row in range(8):
            y = min(height - 1, int((row + 0.5) * height / 8))
            for column in range(8):
                x = min(width - 1, int((column + 0.5) * width / 8))
                pixels.append((Camera.imageGetRed(image, width, x, y)
                               + Camera.imageGetGreen(image, width, x, y)
                               + Camera.imageGetBlue(image, width, x, y)) / 765.0)
        left, right = float(self.left.getValue()), float(self.right.getValue())
        frame = {"CAMERA": pixels,
                 "PROX_LEFT": proximity_vector(left, config["proximity_full_scale"]),
                 "PROX_RIGHT": proximity_vector(right, config["proximity_full_scale"])}
        return frame, {"proximity_left": left, "proximity_right": right,
                       "camera_mean": sum(pixels) / len(pixels)}
