import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ab import Brain
from ab_sdk.__main__ import main
from ab_sdk.design_submit import design_sha256
from design_brain import create_brain


class SDKWorkflowTests(unittest.TestCase):
    def test_native_design_loads_the_saved_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brain = create_brain()
            brain.save(root / "brain.abdesign.json")
            with patch("ab_designer.server.serve") as serve:
                code = main(["design", "--project", temp, "--brain", "brain.abdesign.json", "--no-browser"])
            self.assertEqual(code, 0)
            self.assertEqual(design_sha256(serve.call_args.args[0]), design_sha256(brain))

    def test_native_build_submits_edited_saved_design(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            edited = create_brain().to_dict()
            next(n for n in edited["nodes"] if n["name"] == "TURN_RIGHT")["tnorm"] = 4.9
            brain = Brain.from_dict(edited)
            brain.save(root / "brain.abdesign.json")
            with patch("ab_sdk.__main__.PrimaLuxClient.from_env"), patch("ab_sdk.__main__.build_on_device") as submit:
                submit.return_value = {"status": "READY", "device_ready": True}
                with contextlib.redirect_stdout(io.StringIO()):
                    code = main(["build", "brain", "--project", temp, "--brain", "brain.abdesign.json", "--env", str(root / ".env")])
            self.assertEqual(code, 0)
            self.assertEqual(design_sha256(submit.call_args.args[1]), design_sha256(brain))

    def test_native_run_dispatches_application_and_explicit_env(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "run.py").write_text("print('application entry')\n")
            env = root / "selected.env"
            with patch("ab_sdk.__main__.PrimaLuxClient.from_env") as device, patch("ab_sdk.__main__.subprocess.call") as launch:
                device.return_value.__enter__.return_value.status.return_value = {
                    "engine": {"has_brain": True, "state": "READY", "native_brain_name": "Example"}}
                launch.return_value = 0
                code = main(["run", "-ab", "--project", temp, "--env", str(env)])
            self.assertEqual(code, 0)
            self.assertEqual(launch.call_args.args[0][1], str(root / "run.py"))
            self.assertEqual(launch.call_args.kwargs["env"]["AB_ENV"], str(env))
            self.assertEqual(launch.call_args.kwargs["env"]["AB_UNIFIED_TARGET"], "primalux")


if __name__ == "__main__":
    unittest.main()
