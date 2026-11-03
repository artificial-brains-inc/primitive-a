"""Connect the simulated sensors and wheels to the installed Prima-Lux brain."""
import json
import os
import time
from .sensors import ROOT, OUTPUTS, Sensors, load_config
from .motors import MotorCommands
from .transport import EventBuffer, StopRequested
from .ack import AcknowledgedObservations


def write_state(state, **fields):
    path = ROOT / "logs/run_state.json"
    path.parent.mkdir(exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"state": state, "time": time.time(), **fields}) + "\n")
    temp.replace(path)


def main():
    from controller import Robot
    from ab import ABClient
    from .application import verify_installed, environment_path

    os.chdir(ROOT)
    os.environ["AB_UNIFIED_PROJECT"] = str(ROOT)
    config = load_config()
    stop_path = ROOT / ".stop-request"
    robot = Robot()
    client = session = exchange = log = sensor_log = None
    motors = {}
    stopped = had_error = False
    try:
        for name, device_name in zip(OUTPUTS, ("left wheel motor", "right wheel motor")):
            motor = robot.getDevice(device_name)
            if motor is None:
                raise RuntimeError(f"Missing motor: {device_name}")
            motor.setPosition(float("inf"))
            motor.setVelocity(0.0)
            motors[name] = motor
        verify_installed()
        sensors = Sensors(robot, config["physics_step_ms"])
        if robot.step(config["physics_step_ms"]) == -1:
            return
        client = ABClient.from_env(env_path=environment_path())
        session = client.start_from_env(env_path=environment_path())
        events = EventBuffer(stop_path.exists, timeout_seconds=config["output_timeout_seconds"])
        session.on_output(events.on_output)
        session.on_control(events.on_control)
        commands = MotorCommands(config["wheel_speed_rad_s"])
        run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{time.time_ns()}"
        (ROOT / "logs").mkdir(exist_ok=True)
        log_path = ROOT / "logs" / f"run-{run_id}.jsonl"
        log = log_path.open("x", buffering=1)
        log.write(json.dumps({"kind": "configuration", "config": config}) + "\n")
        sensor_log = (ROOT / "logs" / f"sensors-{run_id}.jsonl").open("x", buffering=1)
        exchange = AcknowledgedObservations(
            session.publish_sensor_frame, events,
            timeout_seconds=config["ack_timeout_seconds"],
            record=lambda record: sensor_log.write(json.dumps(record) + "\n"))
        write_state("RUNNING", log=log_path.name)
        print(f"[ACK] Synchronized: observe, wait for ACK, apply wheels, advance {config['physics_step_ms']} ms.", flush=True)
        last_report = 0.0
        wall_started, sim_started = time.monotonic(), robot.getTime()
        def capture():
            frame, observation = sensors.capture(config)
            observation = dict(observation, source_sim_time=robot.getTime(),
                               capture_monotonic_ns=time.monotonic_ns())
            return frame, observation

        while not stop_path.exists():
            decision = exchange.decide(capture)
            events.check_health()
            commands.apply(decision["decision_frame"])
            observation = decision["observation"]
            # Execute the wheel state delivered with this observation's ACK.
            # No further neural frames or physics steps are awaited first.
            for name, motor in motors.items():
                motor.setVelocity(commands.speeds[name])
            wall_elapsed = time.monotonic() - wall_started
            sim_elapsed = robot.getTime() - sim_started
            log.write(json.dumps({"sim_time": robot.getTime(), "sensors": observation,
                                  "wall_elapsed_seconds": wall_elapsed,
                                  "sim_elapsed_seconds": sim_elapsed,
                                  "exchange_phase": exchange.phase,
                                  "outputs": [decision["decision_frame"]],
                                  "input_sequence": decision["sequence"],
                                  "ack_step": decision["ack_step"],
                                  "decision_step": decision["decision_step"],
                                  "wheel_rad_s": commands.speeds,
                                  "output_delivery": events.stats()}) + "\n")
            now = time.monotonic()
            if now - last_report >= 1:
                last_report = now
                prox = (f"proximity L={observation['proximity_left']:.1f} "
                        f"R={observation['proximity_right']:.1f}")
                ack_step = decision["ack_step"]
                decision_step = decision["decision_step"]
                print(f"[AVOID] sim={robot.getTime():.3f} {prox} "
                      f"wheel L={commands.speeds['WHEEL_LEFT']:.1f} "
                      f"R={commands.speeds['WHEEL_RIGHT']:.1f} "
                      f"ACK={ack_step} decision={decision_step} "
                      f"sim/wall={sim_elapsed / max(wall_elapsed, 1e-9):.2f}x "
                      f"phase={exchange.phase}", flush=True)
            if robot.step(config["physics_step_ms"]) == -1:
                break
    except (StopRequested, KeyboardInterrupt):
        print("Stop requested.", flush=True)
    except Exception as exc:
        had_error = True
        phase = exchange.phase if exchange is not None else "startup"
        print(f"ERROR during {phase}: {type(exc).__name__}: {exc}", flush=True)
    finally:
        for motor in motors.values():
            try:
                motor.setVelocity(0.0)
            except Exception:
                pass
        try:
            robot.step(0)
        except Exception:
            pass
        if session is not None:
            write_state("SAVING")
            try:
                session.stop()
                stopped = True
            except Exception as exc:
                had_error = True
                print(f"Stop/save was not confirmed: {exc}", flush=True)
        elif client is not None:
            try:
                if (client.device.status().get("engine") or {}).get("state") == "RUNNING":
                    client.device.stop_and_wait()
                    stopped = True
            except Exception as exc:
                had_error = True
                print(f"Startup cleanup was not confirmed: {exc}", flush=True)
        if client is not None:
            client.close()
        if log is not None:
            log.close()
        if sensor_log is not None:
            sensor_log.close()
        write_state("ERROR" if had_error else "STOPPED", neural_stop_confirmed=stopped)
        print("Neural Stop/save confirmed." if stopped else "Session ended without Stop/save confirmation.", flush=True)
