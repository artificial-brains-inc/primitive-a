"""Open the Webots body for a brain already built with the SDK."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .sensors import ROOT
from .lifecycle import require_installed, engine_status
from .contracts import INPUT_SIZES, OUTPUT_SIZES

WORLD_PATH = ROOT / "worlds/maze_example_messy.wbt"


def environment_path():
    return Path(os.environ.get("AB_ENV", str(ROOT / ".env"))).expanduser().resolve()


def saved_design(root=ROOT):
    from ab import Brain
    from ab_sdk.design_submit import find_design
    brain = Brain.load(root / "brain.abdesign.json")
    # Runtime discovers this file too; additional exports would be ambiguous.
    find_design(root)
    nodes = brain.to_dict()["nodes"]
    inputs = {n["name"]: n["neurons"] for n in nodes if n["kind"] == "input"}
    outputs = {n["name"]: n["neurons"] for n in nodes if n["kind"] == "output"}
    if inputs != INPUT_SIZES:
        raise ValueError("The saved design must include the robot inputs and TRANSPORT_ACK. Use the matching ACK design and adapter.")
    if outputs != OUTPUT_SIZES:
        raise ValueError("The saved design must include both wheel outputs and TRANSPORT_ACK_OUT. Use the matching ACK design and adapter.")
    return brain


def verify_installed():
    from ab_sdk.primalux import PrimaLuxClient
    from ab_sdk.design_submit import design_sha256
    digest = design_sha256(saved_design())
    with PrimaLuxClient.from_env(environment_path()) as device:
        return require_installed(device.status(), digest)


def controller_report(path):
    try:
        report = json.loads(path.read_text())
        return report if isinstance(report, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def ensure_brain_stopped(timeout=180.0):
    """Confirm native Stop/save even when Webots killed its controller."""
    from ab_sdk.primalux import PrimaLuxClient
    deadline = time.monotonic() + timeout
    with PrimaLuxClient.from_env(environment_path()) as device:
        try:
            status = device.status()
        except Exception:
            # A failed initial status request must not prevent a Stop attempt.
            status = {}
        engine, state = wait_until_idle(device, status, deadline)
        if state == "STOPPED" and not engine.get("busy"):
            engine_status({"engine": engine})
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Automatic Stop/save deadline expired.")
        try:
            result = device.stop_and_wait(timeout=remaining)
        except Exception:
            # The controller may have issued Stop after our initial status
            # read. Confirm that operation instead of sending a blind retry.
            engine, state = wait_until_idle(device, device.status(), deadline)
            if state == "STOPPED" and not engine.get("busy"):
                engine_status({"engine": engine})
                return
            raise
        if result.get("confirmed") is not True or result.get("state") != "STOPPED":
            raise RuntimeError("Prima-Lux did not confirm Stop/save completion.")


def wait_until_idle(device, status, deadline):
    engine = status.get("engine") if isinstance(status, dict) else None
    engine = engine if isinstance(engine, dict) else {}
    state = str(engine.get("state", "")).upper()
    while engine.get("busy"):
        engine_status(status)
        if time.monotonic() >= deadline:
            raise RuntimeError("Prima-Lux remained busy; automatic Stop/save is unconfirmed.")
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
        status = device.status()
        engine, state = engine_status(status)
    return engine, state


def save_launcher_report(**fields):
    path = ROOT / "logs/launcher_state.json"
    try:
        path.parent.mkdir(exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"time": time.time(), **fields}) + "\n")
        temp.replace(path)
    except OSError as exc:
        print(f"Could not write launcher status: {exc}", file=sys.stderr, flush=True)


def launch():
    from launcher_support import find_webots, check_webots, write_controller_runtime, webots_environment
    executable = find_webots(ROOT)
    check_webots(executable)
    verify_installed()
    write_controller_runtime(ROOT)
    (ROOT / ".stop-request").unlink(missing_ok=True)
    state = ROOT / "logs/run_state.json"
    state.unlink(missing_ok=True)
    print("Opening Webots. Closing Webots or pressing Ctrl+C stops Prima-Lux and saves neural dynamics.", flush=True)
    process = subprocess.Popen(
        [executable, "--mode=realtime", str(WORLD_PATH)],
        cwd=ROOT, env=webots_environment(ROOT), start_new_session=True)
    try:
        while process.poll() is None:
            time.sleep(0.25)
    except KeyboardInterrupt:
        (ROOT / ".stop-request").write_text("stop\n")
        print("Stop requested; waiting for the controller to finish...", flush=True)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            report = controller_report(state)
            if report.get("state") in ("STOPPED", "ERROR", "SAVING"):
                break
            if process.poll() is not None:
                break
            time.sleep(0.25)
    finally:
        # This process lives outside Webots. Its cleanup still runs if Webots
        # terminates the controller before the controller's finally block.
        try:
            (ROOT / ".stop-request").write_text("stop\n")
        except OSError as exc:
            print(f"Could not write the controller stop request: {exc}", file=sys.stderr, flush=True)
        print("Webots run ended. Confirming Prima-Lux Stop/save...", flush=True)
        try:
            ensure_brain_stopped()
        except BaseException as exc:
            save_launcher_report(state="STOP_UNCONFIRMED", neural_stop_confirmed=False,
                                 error_type=type(exc).__name__)
            print("Automatic Stop/save is unconfirmed. Check: ab device --env .env status", file=sys.stderr, flush=True)
            raise
        save_launcher_report(state="STOPPED", neural_stop_confirmed=True)
        print("Prima-Lux Stop/save confirmed. You can close any remaining Webots window.", flush=True)
    report = controller_report(state)
    if report.get("state") == "ERROR":
        raise RuntimeError("The controller reported an error; Prima-Lux is stopped. Inspect logs/run_state.json.")
    if process.returncode not in (None, 0):
        raise RuntimeError(f"Webots exited with code {process.returncode}; Prima-Lux is stopped.")


def main():
    try:
        os.chdir(ROOT)
        launch()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
