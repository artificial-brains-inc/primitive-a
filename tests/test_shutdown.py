import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from avoidance import application


def status(state="RUNNING", busy=False):
    return {"engine": {"state": state, "busy": busy, "available": True}}


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.device = MagicMock()
        self.device.__enter__.return_value = self.device
        self.device.status.return_value = status()
        self.device.stop_and_wait.return_value = {"confirmed": True, "state": "STOPPED"}
        self.factory = self.enterContext(patch("ab_sdk.primalux.PrimaLuxClient.from_env", return_value=self.device))
        self.enterContext(patch.object(application.time, "sleep"))

    def test_running_brain_uses_sdk_stop_and_wait_with_selected_env(self):
        with patch.dict("os.environ", {"AB_ENV": "/tmp/selected-demo.env"}):
            application.ensure_brain_stopped()
        self.factory.assert_called_once_with(Path("/tmp/selected-demo.env"))
        self.device.stop_and_wait.assert_called_once()

    def test_idle_stopped_brain_needs_no_duplicate_stop(self):
        self.device.status.return_value = status("STOPPED")
        application.ensure_brain_stopped()
        self.device.stop_and_wait.assert_not_called()

    def test_in_progress_save_is_allowed_to_finish(self):
        self.device.status.side_effect = [status("RUNNING", True), status("STOPPED", True), status("STOPPED")]
        application.ensure_brain_stopped()
        self.device.stop_and_wait.assert_not_called()
        self.assertEqual(self.device.status.call_count, 3)

    def test_failed_initial_status_does_not_prevent_stop_attempt(self):
        self.device.status.side_effect = OSError("Temporary connection failure")
        application.ensure_brain_stopped()
        self.device.stop_and_wait.assert_called_once()

    def test_malformed_initial_status_does_not_prevent_stop_attempt(self):
        for report in (None, {}, {"engine": "unusable"}):
            with self.subTest(report=report):
                self.device.status.return_value = report
                self.device.stop_and_wait.reset_mock()
                application.ensure_brain_stopped()
                self.device.stop_and_wait.assert_called_once()

    def test_racing_controller_stop_can_be_confirmed_without_retry(self):
        self.device.status.side_effect = [status(), status("STOPPED", True), status("STOPPED")]
        self.device.stop_and_wait.side_effect = RuntimeError("Stop already in progress")
        application.ensure_brain_stopped()
        self.device.stop_and_wait.assert_called_once()

    def test_ready_or_request_acceptance_alone_is_not_save_confirmation(self):
        for result in ({"ok": True}, {"confirmed": True, "state": "READY"}):
            with self.subTest(result=result):
                self.device.stop_and_wait.return_value = result
                with self.assertRaisesRegex(RuntimeError, "did not confirm"):
                    application.ensure_brain_stopped()

    def test_busy_save_timeout_is_reported(self):
        self.device.status.return_value = status("STOPPED", True)
        with self.assertRaisesRegex(RuntimeError, "remained busy"):
            application.ensure_brain_stopped(timeout=0)
        self.device.stop_and_wait.assert_not_called()

    def launch_case(self, report=None, exitcode=0, interrupt=False, stop_error=None, popen_error=None):
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            root = Path(temp)
            (root / "logs").mkdir()
            process = Mock(returncode=exitcode)
            def poll():
                # Simulate the controller writing its report after launch.
                if report is not None:
                    (root / "logs/run_state.json").write_text(report)
                if interrupt:
                    process.poll.side_effect = lambda: exitcode
                    raise KeyboardInterrupt
                return exitcode
            process.poll.side_effect = poll
            stack.enter_context(patch.object(application, "ROOT", root))
            stack.enter_context(patch.object(application, "verify_installed"))
            for name in ("find_webots", "check_webots", "write_controller_runtime", "webots_environment"):
                stack.enter_context(patch("launcher_support." + name))
            stack.enter_context(patch.object(application.subprocess, "Popen", return_value=process, side_effect=popen_error))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            if stop_error:
                self.device.stop_and_wait.side_effect = stop_error
            if stop_error or popen_error or exitcode:
                with self.assertRaises((RuntimeError, OSError)):
                    application.launch()
            else:
                application.launch()
            path = root / "logs/launcher_state.json"
            return json.loads(path.read_text()) if path.exists() else None

    def test_gui_close_confirms_device_despite_missing_malformed_or_stale_report(self):
        for report in (None, "{", '{"state":"STOPPED","neural_stop_confirmed":true}'):
            with self.subTest(report=report):
                self.device.stop_and_wait.reset_mock()
                result = self.launch_case(report=report)
                self.assertEqual(result["state"], "STOPPED")
                self.assertTrue(result["neural_stop_confirmed"])
                self.device.stop_and_wait.assert_called_once()

    def test_abrupt_webots_exit_still_stops_before_reporting_exit_error(self):
        result = self.launch_case(exitcode=9)
        self.assertTrue(result["neural_stop_confirmed"])
        self.device.stop_and_wait.assert_called_once()

    def test_control_c_also_confirms_stop(self):
        result = self.launch_case(interrupt=True)
        self.assertTrue(result["neural_stop_confirmed"])
        self.device.stop_and_wait.assert_called_once()

    def test_failed_stop_is_recorded_unconfirmed(self):
        result = self.launch_case(stop_error=RuntimeError("Device unreachable"))
        self.assertEqual(result["state"], "STOP_UNCONFIRMED")
        self.assertFalse(result["neural_stop_confirmed"])

    def test_failure_to_launch_webots_does_not_stop_an_unrelated_session(self):
        self.assertIsNone(self.launch_case(popen_error=OSError("Cannot launch")))
        self.device.stop_and_wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
