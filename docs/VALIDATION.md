# Observe and validate the lesson

Run local checks with `python -m unittest discover -s tests -v`. These checks exercise the real
SDK's public design and actuation decoder, graph wiring, sensor encoding,
output delivery and lifecycle guards. They do not simulate synthetic neurons.

Installation checks create real virtual environments without pip and verify
repair and preservation of existing files. SDK workflow checks exercise design,
build and run command routing with device calls replaced by test doubles.
They verify that saved design edits reach the build command; they do not
compile on a real device or launch Webots.

The course check verifies the experiment world's contents, allowing only the
controller name to differ. Primitive A checks cover the single camera Theta
stage, the two-stage proximity pathways and both directions of turn inhibition.

ACK checks cover atomic submission, a fresh acknowledgement, execution using
the ACK frame without consuming later frames, stale or absent ACK, a stuck ACK
output, overlapping submission, stop interruption and ACK arriving before its
HTTP queue receipt returns. Scripted frames test the protocol, not the compiled
circuit's dynamics.

The bridge integration test verifies one body step per ACK, no body advancement
while waiting, configurable movement durations of 16, 32, 64 and 128 ms,
immediate wheel execution at that ACK step, and Stop/save after
timeouts or missing frames. Launcher tests cover normal window closure, Ctrl+C,
abrupt Webots exit, missing/stale controller reports, an already-running save,
concurrent Stop and failed Stop confirmation. Device calls are test doubles;
these tests do not measure live simulation speed or hardware response latency.

Then compile and run on Prima-Lux with Webots R2025a. Use the same scene and
wheel speed when comparing versions. Save the run logs with each observation.

| Scenario | What to inspect |
| --- | --- |
| Clear front space and illuminated scene | Camera activity reaches the forward pathway; both wheel outputs can activate. |
| Front-right obstacle | Right proximity input rises; left-turn pathway changes the left wheel output and the body turns left. |
| Front-left obstacle | Mirrored response and right turn. |
| Similar evidence on both sides | Observe the competition, including stalls or oscillation; there is no software tie-breaker. |
| Obstacle removed | Observe inhibition release and renewed forward activity. |
| Reduced camera activity | Observe the forward drive's dependence on the scene input. |
| Explicit zero-count output frame | Previously active wheel command becomes zero. |
| Stop or lost output stream | Motors are zeroed; the controller attempts Stop/save and reports whether it succeeded. |
| First and subsequent observations | ACK clears before submission; the next fresh ACK immediately supplies the wheel command for one physics step. No body step occurs while waiting. |
| Longer movement per ACK | With `physics_step_ms` set to 32 or 64, each ACK advances exactly that duration. Inspect the added travel before the next sensor observation. |
| Simulation pacing | Check `ACK` equals `decision` and compare capture-to-ACK latency. `sim/wall` reflects the synchronized loop's actual pace. |
| Close the Webots window | The terminal confirms Prima-Lux Stop/save and `ab device --env .env status` reports STOPPED and idle. |
| Controller exits before saving | The launcher independently checks the device and completes Stop/save after Webots closes. |
| Device unavailable during shutdown | The command reports Stop/save as unconfirmed and records that result in `logs/launcher_state.json`. |
| ACK missing or stuck active | No new observation is sent; the controller stops with the failing phase in the log. |

The robot has only two front proximity sensors. This project does not provide
full-body clearance sensing, a maze planner or a guaranteed collision-free
navigation policy. It is a small circuit to inspect and extend.

The public Brain design must be compiled and behaviorally checked after any
change to the graph, sensor calibration, output interpretation or timing.
Local test success alone is not a device behavior result.
