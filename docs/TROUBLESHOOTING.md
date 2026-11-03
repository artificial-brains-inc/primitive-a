# Troubleshooting

- **No module named pip:** run `bash install.sh` again. It restores pip inside
  the existing project environment using ensurepip before installing dependencies.
  If system venv/ensurepip support is missing, it installs the Ubuntu Python
  prerequisites first.
- **ab: command not found:** run `source .venv/bin/activate` in this terminal.
- **Webots is missing or the version differs:** install R2025a separately, or
  set `WEBOTS_EXECUTABLE` in `.env` to your existing R2025a executable.
- **The controller module is missing:** run `ab run -ab --env .env`. Webots,
  which the application opens, supplies this module to its controller.
- **The device cannot be reached:** check `.env`, then use
  `ab device --env .env status`.
- **The installed design differs:** save your intended design as
  `brain.abdesign.json`, stop the active session, then run
  `ab build brain --brain brain.abdesign.json --env .env`.
- **Missing TRANSPORT_ACK or TRANSPORT_ACK_OUT:** the saved or installed graph
  does not match the controller's ACK contract. Build the complete supplied
  design, including its isolated ACK component.
- **ACK clear or neural ACK timeout:** inspect the phase reported in
  the console and the latest `logs/sensors-*.jsonl`. Verify the ACK output rises
  after the atomic observation and clears through its feedback path. Increasing
  the timeout does not replace an absent ACK. The controller stops rather than
  resending an observation whose processing status is unknown.
- **Designer edits are missing from the build:** Save brain downloads a file.
  Replace the project's `brain.abdesign.json` with that download before building.
  Do not run `python design_brain.py` unless you intend to use its construction.
- **More than one design found:** keep one `*.abdesign.json` file in the project
  root. Move other exports to a subfolder.
- **The robot does not move:** inspect camera activity, sensor logs and wheel
  output counts. Camera activity supplies forward drive in this circuit.
  Check that new Prima-Lux output steps arrive.
- **Execution is very slow:** check that the console shows the same `ACK` and
  `decision` step. The controller executes at ACK without an additional readout
  delay. Compare sensor-send and ACK timestamps in `logs/sensors-*.jsonl` to
  measure the wait; `sim/wall` reports the resulting simulation pace. The body
  stays synchronized with the brain. Increasing wheel speed changes travel per
  simulated second, not neural ACK latency.
- **More movement per ACK:** increase `physics_step_ms` from 32 to 64 or 128 and
  restart. Use a positive integer multiple of 16. This extends each acknowledged
  movement without letting the body run while ACK is pending; the next sensor
  observation happens after the configured movement duration.
- **A wheel stays on:** inspect both the turn-to-motor and turn-to-output
  inhibition. An internal population and its bistable output have different
  clearing requirements.
- **Both wheels stop near a symmetric obstacle:** inspect the inputs and
  competing populations; this circuit has no software escape planner.
- **The output stream times out or skips steps:** inspect the connection and
  device status before restarting.
- **Webots closed before Stop/save confirmation:** leave the `ab run` terminal
  open; the launcher independently checks the device and waits for Stop/save.
  If it reports an error, inspect `logs/launcher_state.json`, then use
  `ab device --env .env status` and `ab device --env .env stop` if still running.
  Automatic cleanup requires the launcher process to remain alive and the
  device to be reachable.
