# Primitive A: front obstacle avoidance with Prima-Lux

Connect a simulated differential-drive robot to synthetic neurons running on
Prima-Lux. Build a sensory primitive, see how it changes wheel activity, and
learn how to connect a goal to supporting and opposing neural pathways.

**GET SYNTHETIC NEURONS:** [Prima-Lux Dev Kit with capacity up to 10,000 synthetic neurons](https://artificialbrains.ai)

The robot has a camera, eight proximity sensors and two driven wheels.
Primitive A uses the camera and the two front sensors, `proximity_left` and
`proximity_right`; the other proximity sensors remain available for extensions.
Camera activity supports forward movement. Proximity activity recruits turn
pathways that inhibit one wheel so the robot can turn away from a front obstacle.

**Lesson:** a sensory primitive becomes useful when its result can influence an
action. The same result can later connect to other goals and motor primitives.

## What you need

| Requirement | Details |
| --- | --- |
| Computer | Ubuntu 24.04, x86_64, with a graphical desktop and OpenGL |
| Git | Installed locally for cloning the repository |
| Python | Python 3.11 or newer with `venv`; Python 3.12 recommended |
| Webots | R2025a, downloaded and installed separately on your computer |
| Prima-Lux | Onboarded device reachable from your computer, plus its developer API key |
| SDK | `artificialbrains_sdk==0.4.0`, installed by `install.sh` |
| Internet | Needed for initial dependency installation and brain compilation |

The body is simulated in Webots. The neural dynamics run on your Prima-Lux.
You do not need a physical e-puck. The included world has all geometry and
robot devices in one file and does not download robot PROTO files.

The experiment runs in `worlds/maze_example_messy.wbt`, a household/factory
obstacle course with furniture, underpasses, narrow gaps and a blue start marker.
The saved robot pose, viewpoint, geometry, materials and sensor settings are
part of this world. The green marker is a landmark, not a navigation target.

## Clone, install, design, build and run

Install [Webots R2025a](https://github.com/cyberbotics/webots/releases/tag/R2025a)
separately on your computer, or reuse your existing installation.

### 1. Clone

Replace `REPOSITORY_URL` with this repository's HTTPS clone URL from GitHub:

```bash
git clone REPOSITORY_URL primalux-front-obstacle-webots
cd primalux-front-obstacle-webots
```

### 2. Install the project dependencies

```bash
bash install.sh
source .venv/bin/activate
```

The installer creates or repairs this project's virtual environment, restores
`pip` when it is missing, and installs the SDK and its Python dependencies.
On Ubuntu, it installs missing Python venv/pip system packages using apt and
may ask for sudo. It preserves an existing `.env` and saved brain design.
Webots is never downloaded, installed or updated by this package.

The installer creates `.env` from the example if needed. Open `.env` in a text
editor and set your onboarded Prima-Lux address and developer API key:

```dotenv
AB_DEVICE_URL=http://prima-lux.local:8080
AB_DEVICE_API_KEY=YOUR_PRIMA_LUX_DEVELOPER_API_KEY
AB_TELEMETRY=true
```

Use your device's actual address if the hostname is unavailable. The API key
comes from your Prima-Lux interface. Keep `.env` private; it is excluded from Git.

### 3. Open the design in the SDK

```bash
ab design --brain brain.abdesign.json --env .env
```

The SDK opens its Canvas and Python editor with the brain named **Primitive A**.
Follow CAMERA through CAMERA_RELAY and the single CAMERA_SCENE Theta population
to the two forward motor pathways, then PROX_RIGHT through its two Theta stages
to TURN_LEFT and the corresponding inhibitory connections. Inspect the rhythms
and TNorm values before changing them.

For the first run, inspect the supplied design unchanged. Close the Designer
with Ctrl+C in its terminal when finished.

**If you edit the design:** use **Save brain** in the Designer. SDK 0.4.0
downloads a file; it does not overwrite the project file automatically. Save
the edited file as this project's `brain.abdesign.json` before building.
With the supplied brain name, the download is `primitive-a.abdesign.json`:

```bash
cp "$HOME/Downloads/primitive-a.abdesign.json" brain.abdesign.json
```

Use the actual downloaded filename if you renamed the brain. Keep one
`*.abdesign.json` file in the project root so the SDK can discover it at runtime.

### 4. Build on Prima-Lux

```bash
ab build brain --brain brain.abdesign.json --env .env
```

Wait for the SDK to confirm that the brain is installed and READY. This step
compiles the saved public design through Prima-Lux; it does not open Webots.

### 5. Run

```bash
ab run -ab --env .env
```

The SDK runs the project's `run.py`. That application opens your existing
Webots installation and connects its sensors and motors to the installed brain.
It does not install dependencies, regenerate a design or submit a build.

The controller sends one observation with its ACK pulse and waits for a fresh
neural ACK. As soon as that ACK arrives, it applies the wheel states from the
same output frame and advances Webots by `physics_step_ms` (32 ms by default).
It then repeats
with a new observation, after the ACK output has cleared.

The body does not advance while waiting for the brain. There is no additional
readout window after ACK. See [ACK synchronization](docs/ACK.md).

For more movement per ACK, set `physics_step_ms` to `64` or `128` in `config.json`
and restart the run. At `64`, each acknowledged command runs for 64 ms of
simulation time—twice the default duration. The body still waits for the
next ACK before moving again. Larger values mean more travel between sensor
observations. Keep your chosen `wheel_speed_rad_s` setting.

Use a positive integer multiple of 16. The world's underlying physics interval
stays at 16 ms; this setting controls how much simulated time each acknowledged
command advances. See Webots' [control-step documentation](https://cyberbotics.com/doc/guide/controller-programming?version=R2025a).

The application uses Webots on PATH or in a common installation directory.
For a custom location, add the executable path to `.env`:

```dotenv
WEBOTS_EXECUTABLE=/absolute/path/to/webots
```

For later sessions, activate `.venv` and use `ab run -ab --env .env`.
Repeat the design and build steps when changing the brain. See
[requirements](docs/REQUIREMENTS.md) for the supported environment.

## Observe the sensory primitive

The supplied [Primitive A design](docs/PRIMITIVE_A.md) has 21 populations and
25 directed connections: the 17-population avoidance circuit plus an isolated
four-population transport ACK circuit. Its camera pathway contains one Theta population;
each proximity pathway contains two. The two turn populations inhibit each
other and inhibit the matching forward motor population and wheel output.

Follow one side through [design_brain.py](design_brain.py):

1. `PROX_RIGHT` carries the front-right proximity observation as 16 ordered values.
2. A high-gamma relay feeds Theta T3, then Theta T2.01.
3. Theta T2.01 excites the Beta T5 `TURN_LEFT` population.
4. `TURN_LEFT` inhibits `FORWARD_LEFT` and clears `WHEEL_LEFT`.
5. With the right wheel active and the left wheel suppressed, the body turns left.

The left sensor has a mirrored pathway. `TURN_LEFT` and `TURN_RIGHT` inhibit
each other, allowing competing turn activity to interact inside the brain.
The controller never compares the two sensor readings to choose a turn.

The console shows proximity readings, applied wheel velocities, ACK step,
decision step and `sim/wall` (simulation time divided by elapsed wall time).
`ACK` and `decision` must show the same neural step: execution uses that ACK
frame immediately. Wall-clock speed depends on neural ACK latency; the simulator
does not run ahead to compensate. Each run
writes sensor and output records to `logs/`. Observe the changing response over
time; a single silent timestep does not describe a rhythmic population.
With `AB_TELEMETRY=true` in `.env`, the SDK opens its local neuron-telemetry
view. Use it to inspect the named sensory, turn and forward populations.

The green floor marker is a visual landmark. This brain has no destination
input or maze-solving circuit, so arriving at that marker is not its goal.

## How to build a goal

Start with a condition you want the body to maintain or reach, then describe
what observations and actions matter to it. A goal is implemented through the
neural connections that support, oppose and end actions.

For this example, the intended behavior is **move through the environment
while turning away from obstacles detected in front**.

| Design question | This project's answer |
| --- | --- |
| What supplies activity for movement? | Camera input passes through the scene pathway to both forward motor populations. |
| What provides evidence that the movement should change? | Independent front-left and front-right proximity pathways. |
| Which action helps with right-side obstacle evidence? | A left turn, expressed by suppressing the left wheel while the right stays active. |
| Which action helps with left-side obstacle evidence? | The mirrored right turn. |
| Where is the decision expressed? | In the turn and motor populations, then the two wheel outputs. |
| What makes an action end? | Inhibition reaches both the motor population and its bistable output; continuing scene activity can recruit forward movement again. |

This goal is built into the circuit. There is no text prompt or target coordinate
in `config.json`. Wheel speed changes the physical expression of an active
output; it does not define the goal. Camera brightness is sensory drive here,
not object recognition or a guarantee of sustained forward movement in darkness.

For a new goal such as reaching a light, identify the new observations, build
the sensory and comparison pathways, and connect their evidence to candidate
actions. Keep the observations separate from the neural conclusions. For
example, provide measured and target positions separately when the brain is
meant to compare them.

## How goals should interact

Choose relationships at the actions where goals meet. Two goal labels do not
need a generic winner. Some actions help both goals; some compete; some must
be suppressed in a particular context.

| Relationship | When to use it | Connection to this example |
| --- | --- | --- |
| Agreement | Evidence supports the same candidate action. | Scene activity supports both forward wheel pathways. A later goal may also support a compatible action. |
| Contradiction | Evidence opposes an action, but need not completely suppress it. | Use opposing evidence when tradeoffs are acceptable; do not describe every inhibitory link as a guaranteed veto. |
| Veto | A condition should suppress a specified action. | A turn pathway inhibits one forward motor population and its held output. Verify suppression and recovery in the running circuit. |
| Competition | Two actions are incompatible in the current body. | The left-turn and right-turn populations inhibit one another. |
| Cooperation | Actions can help at the same time. | The two forward wheel outputs can remain active together. |
| Sequence | A later action depends on the state reached by an earlier one. | Adding approach-then-grasp needs an observed completion condition and a defined transition; it is a later lesson. |

**Work through a conflict before wiring it.** Suppose the target is on the right
but an obstacle is also on the right. Write down which movement helps approach,
which movement clears the obstacle, which pathway must be inhibited, and what
observation allows approach to resume. Then connect those relationships in the
brain and test that exact situation.

Keep three choices explicit: the evidence entering a decision, the relationship
between competing actions, and the lifetime of each output. See
[Building and connecting goals](docs/GOALS.md) for a worked design exercise.

## Change and rebuild the brain

Edit the design using `ab design`, save the downloaded design into the project,
then build and run using the SDK:

```bash
ab build brain --brain brain.abdesign.json --env .env
ab run -ab --env .env
```

For learning the public Python API, read `design_brain.py`. It uses `Brain`,
`input()`, `opu()`, `output()` and `connect()` to construct the supplied circuit.
If you choose to edit that Python source, explicitly regenerate the JSON:

```bash
python design_brain.py
ab design --brain brain.abdesign.json --env .env
```

Running `design_brain.py` overwrites `brain.abdesign.json` with the Python
construction. Use that step only when the Python source is the design you
intend to build. Installation and application startup leave Designer edits intact.

Inhibition defaults to its reference strength. Increasing inhibition does not
mean that the same percentage of neurons will stop firing. Observe suppression
and recovery rather than assuming them.

Start from the public
[Guide to Building an Artificial Brain](https://github.com/artificial-brains-inc/Guide-to-Building-an-Artificial-Brain)
and [Artificial Brains SDK](https://github.com/artificial-brains-inc/artificial_brains).

## Stop and neural state

**Close the Webots window**, or press **Ctrl+C in the terminal running
`ab run`**. The launcher automatically uses the SDK to stop Prima-Lux and waits
for the device to report STOPPED with no operation in progress. It checks the
device even if Webots terminates its controller before cleanup can finish.
Keep the terminal open until it prints **Prima-Lux Stop/save confirmed**.

The normal run command enables this cleanup; there is no separate watcher or
launcher command. `logs/launcher_state.json` records the result. If the device
cannot confirm Stop/save, the command reports an error instead of claiming
success. To stop from a second activated terminal:

```bash
ab device --env .env stop
```

Check the device using:

```bash
ab device --env .env status
```

Stop saves neural dynamics. The robot's position in Webots is a separate state.
The application does not reset neural dynamics automatically. For a fresh
experiment after stopping, explicitly request a reset:

```bash
ab device --env .env reset-dynamics
ab device --env .env status
```

A reset request can be asynchronous. Wait until device status reports an idle
READY or STOPPED state with no pending operation before running again.

## Try it yourself

1. Place an obstacle in front-right space, then front-left space. Follow the
   corresponding sensory path, wheel output and physical turn.
2. Change `wheel_speed_rad_s` from 3.0 to 2.0 in `config.json`. Compare travel
   per response without changing the neural goal.
3. Inspect what happens when both front sensors carry similar evidence.
   Do not assume mutual inhibition guarantees a useful turn in every symmetric situation.
4. In a copy of the design, remove one direct turn-to-wheel inhibitory edge.
   Observe why suppressing an internal OPU may fail to clear an already active output.
5. Design a light-approach goal on paper. Use the conflict table in
   [GOALS.md](docs/GOALS.md) before adding its connections.

## Checks and project files

```bash
python -m unittest discover -s tests -v
ab device --env .env status
```

Local tests cover the public graph, sensor encoding, output decoding and device
lifecycle checks. They do not establish collision-free behavior. Compilation
and behavior checks require Webots and Prima-Lux; follow the scenarios in
[VALIDATION.md](docs/VALIDATION.md).

| File | Purpose |
| --- | --- |
| `design_brain.py` | Readable neural construction; start your edits here |
| `brain.abdesign.json` | Generated public design sent to the compiler |
| `config.json` | Movement duration per ACK, sensor scaling, wheel speed and transport timeouts |
| `avoidance/sensors.py` | Physical measurements and fixed input encoding |
| `avoidance/motors.py` | SDK output decoding and wheel mapping |
| `avoidance/ack.py` | One observation, one ACK, immediate wheel execution |
| `avoidance/application.py` | Opens Webots and confirms Stop/save when the run ends |
| `run.py` | Application entry point used by `ab run` |
| `avoidance/bridge.py` | Simulator/device connection and run logs |
| `worlds/maze_example_messy.wbt` | Experiment obstacle course and robot |
| `docs/PRIMITIVE_A.md` | Primitive A pathways, operating points and body mapping |

Continue with the [teaching project sequence](docs/LEARNING_PATH.md).
