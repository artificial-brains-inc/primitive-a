import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ab import Brain
from design_brain import create_brain, ROOT
from avoidance.sensors import proximity_vector, load_config
from avoidance.motors import MotorCommands
from avoidance.transport import EventBuffer, StopRequested
from avoidance.lifecycle import require_installed
from avoidance.application import saved_design, WORLD_PATH
from avoidance.contracts import ACK_OUTPUT, INPUT_SIZES


def output(step, left, right, ack=0):
    return {"step": step, "actuation": {"channels": {
        "WHEEL_LEFT": left, "WHEEL_RIGHT": right, ACK_OUTPUT: ack}}}


def report(state="READY", digest="expected", busy=False):
    return {"engine": {"state": state, "has_brain": True, "busy": busy},
            "package": {"active": {"design_sha256": digest}}}


class DesignTests(unittest.TestCase):
    def test_public_design_roundtrip(self):
        brain = create_brain()
        brain.validate()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "brain.abdesign.json"
            brain.save(path)
            self.assertEqual(Brain.load(path).to_dict(), brain.to_dict())
        Brain.load(ROOT / "brain.abdesign.json").validate()

    def test_sensor_contract_and_mirrored_turns(self):
        design = create_brain().to_dict()
        nodes = {n["name"]: n for n in design["nodes"]}
        self.assertEqual({n["name"]: n["neurons"] for n in design["nodes"] if n["kind"] == "input"},
                         INPUT_SIZES)
        edges = {(e["from"], e["to"], e["type"]) for e in design["connections"]}
        for sensor, turn in (("PROX_LEFT", "RIGHT"), ("PROX_RIGHT", "LEFT")):
            self.assertEqual(nodes[sensor + "_T1"]["tnorm"], 3)
            self.assertEqual(nodes[sensor + "_T2"]["tnorm"], 2.01)
            self.assertIn((sensor + "_T2", "TURN_" + turn, "exc"), edges)
            self.assertIn(("TURN_" + turn, "FORWARD_" + turn, "inh"), edges)
            self.assertIn(("TURN_" + turn, "WHEEL_" + turn, "inh"), edges)
        self.assertIn(("TURN_LEFT", "TURN_RIGHT", "inh"), edges)
        self.assertIn(("TURN_RIGHT", "TURN_LEFT", "inh"), edges)

    def test_primitive_a_has_one_scene_theta_and_two_proximity_stages(self):
        design = create_brain().to_dict()
        self.assertEqual(design["name"], "Primitive A")
        nodes = {node["name"]: node for node in design["nodes"]
                 if not node["name"].startswith("TRANSPORT_ACK")}
        self.assertEqual(len(nodes), 17)
        edges = {(e["from"], e["to"], e["type"]) for e in design["connections"]
                 if e["from"] in nodes and e["to"] in nodes}
        self.assertEqual(len(edges), 20)
        self.assertEqual(nodes["CAMERA_SCENE"]["rhythm"], "theta")
        self.assertEqual(nodes["CAMERA_SCENE"]["tnorm"], 3)
        self.assertNotIn("CAMERA_T1", nodes)
        self.assertNotIn("CAMERA_T2", nodes)
        self.assertIn(("CAMERA_RELAY", "CAMERA_SCENE", "exc"), edges)
        self.assertEqual({e for e in edges if e[0] == "CAMERA_SCENE"},
                         {("CAMERA_SCENE", "FORWARD_LEFT", "exc"),
                          ("CAMERA_SCENE", "FORWARD_RIGHT", "exc")})

    def test_world_is_self_contained_and_uses_project_controller(self):
        world = WORLD_PATH.read_text()
        self.assertTrue(world.startswith("#VRML_SIM R2025a"))
        self.assertNotIn("EXTERNPROTO", world)
        self.assertIn('controller "primalux_front_obstacle"', world)
        for name in ("proximity_left", "proximity_right", "left wheel motor", "right wheel motor"):
            self.assertTrue('name "' + name + '"' in world, f"Missing device: {name}")
        # Camera's default device name in Webots R2025a is "camera".
        self.assertIn("Camera {", world)
        load_config()

    def test_course_matches_experiment_world_except_controller_binding(self):
        # Fingerprint of the supplied experiment world. The controller name
        # is the only change required to connect it to this project.
        source_world = WORLD_PATH.read_bytes().replace(
            b'controller "primalux_front_obstacle"', b'controller "maze_example"')
        self.assertEqual(hashlib.sha256(source_world).hexdigest(),
                         "c9c40f082c216f1e010b47df7c9786b00c222e58ab3549609ec3cdea15e72778")


class TranslationTests(unittest.TestCase):
    def test_movement_duration_accepts_multiples_of_world_basic_step(self):
        config = load_config()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("avoidance.sensors.ROOT", root):
                for step in (16, 32, 64, 128):
                    with self.subTest(step=step):
                        (root / "config.json").write_text(json.dumps(dict(config, physics_step_ms=step)))
                        self.assertEqual(load_config()["physics_step_ms"], step)
                for step in (0, -16, 8, 24, 16.0, True, None):
                    with self.subTest(step=step):
                        (root / "config.json").write_text(json.dumps(dict(config, physics_step_ms=step)))
                        with self.assertRaisesRegex(ValueError, "multiple of 16"):
                            load_config()

    def test_proximity_scale_saturation_and_direction(self):
        for raw, active in ((0, 0), (250, 4), (500, 8), (1000, 16), (1500, 16)):
            values = proximity_vector(raw, 1000)
            self.assertEqual(values, [1.0] * active + [0.0] * (16 - active))
        for raw in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                proximity_vector(raw, 1000)

    def test_real_sdk_decodes_turns_and_zero_clears_previous_motion(self):
        commands = MotorCommands(3.0)
        self.assertEqual(commands.apply(output(1, 1, 1)), {"WHEEL_LEFT": 3.0, "WHEEL_RIGHT": 3.0})
        self.assertEqual(commands.apply(output(2, 0, 1)), {"WHEEL_LEFT": 0.0, "WHEEL_RIGHT": 3.0})
        self.assertEqual(commands.apply(output(3, 1, 0)), {"WHEEL_LEFT": 3.0, "WHEEL_RIGHT": 0.0})
        self.assertEqual(commands.apply(output(4, 0, 0)), {"WHEEL_LEFT": 0.0, "WHEEL_RIGHT": 0.0})
        with self.assertRaises(ValueError):
            commands.apply(output(4, 1, 1))

    def test_bad_output_contract_does_not_become_motion(self):
        for event in ({"step": 1}, output(1, 2, 0), output(1, True, 0)):
            with self.assertRaises(ValueError):
                MotorCommands(3).apply(event)

    def test_output_buffer_preserves_zero_and_detects_missing_step(self):
        events = EventBuffer()
        events.on_output(output(10, 1, 1))
        events.on_output(output(11, 0, 0))
        self.assertEqual(events.take_one()[0][1]["step"], 10)
        self.assertEqual(events.take_one()[0][1]["actuation"]["channels"]["WHEEL_LEFT"], 0)
        self.assertEqual(events.take_one(), [])
        events.on_output(output(13, 1, 1))
        with self.assertRaises(RuntimeError):
            events.take_one()

    def test_timeout_and_remote_stop(self):
        clock = [0.0]
        events = EventBuffer(timeout_seconds=5, clock=lambda: clock[0])
        clock[0] = 5.1
        with self.assertRaises(RuntimeError):
            events.take_one()
        events = EventBuffer()
        events.on_control({"command": "stop"})
        with self.assertRaises(StopRequested):
            events.take_one()


class LifecycleTests(unittest.TestCase):
    def test_run_rejects_running_busy_or_wrong_brain(self):
        self.assertEqual(require_installed(report(), "expected"), "READY")
        for item in (report("RUNNING"), report(busy=True), report(digest="other")):
            with self.assertRaises(RuntimeError):
                require_installed(item, "expected")

    def test_designer_edit_is_loaded_without_regenerating_python_design(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            edited = create_brain().to_dict()
            next(node for node in edited["nodes"] if node["name"] == "TURN_LEFT")["tnorm"] = 4.9
            Brain.from_dict(edited).save(root / "brain.abdesign.json")
            loaded = saved_design(root).to_dict()
            self.assertEqual(next(node for node in loaded["nodes"] if node["name"] == "TURN_LEFT")["tnorm"], 4.9)


if __name__ == "__main__":
    unittest.main()
