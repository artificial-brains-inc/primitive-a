# Primitive A

Primitive A connects scene activity to forward movement and front proximity
activity to competing turns. The avoidance circuit has three sensory inputs,
twelve OPUs, two wheel outputs and twenty directed connections. An isolated
transport ACK component adds one input, two OPUs, one output and five connections.
The complete public design has 21 populations and 25 connections.

## Input and body mapping

| Input or output | Webots device | Representation |
| --- | --- | --- |
| CAMERA | `camera` | 64 normalized grayscale samples in an 8 by 8 grid |
| PROX_RIGHT | `proximity_right` | 16 cumulative values representing front-right proximity |
| PROX_LEFT | `proximity_left` | 16 cumulative values representing front-left proximity |
| WHEEL_LEFT | `left wheel motor` | Active output maps to the configured forward speed; zero maps to zero speed |
| WHEEL_RIGHT | `right wheel motor` | Active output maps to the configured forward speed; zero maps to zero speed |
| TRANSPORT_ACK | Controller transport marker | One pulse included in each atomic observation |
| TRANSPORT_ACK_OUT | Neural acknowledgement | Confirms the submitted marker reached the neural circuit; never mapped to a motor |

The world has eight proximity sensors. This primitive reads only
`proximity_left` and `proximity_right`. It does not use collision, rear-sensor
input to choose movement. The ACK circuit controls when a new observation can
be sent and when the body advances; it has no connections to the avoidance
circuit. Webots waits for ACK before executing each movement step.

## Build the three pathways

| Pathway | Excitatory sequence | Purpose |
| --- | --- | --- |
| Scene | CAMERA → CAMERA_RELAY → CAMERA_SCENE → both FORWARD populations → matching WHEEL outputs | Supply activity for forward movement |
| Right proximity | PROX_RIGHT → PROX_RIGHT_RELAY → PROX_RIGHT_T1 → PROX_RIGHT_T2 → TURN_LEFT | Recruit a left turn from right-side evidence |
| Left proximity | PROX_LEFT → PROX_LEFT_RELAY → PROX_LEFT_T1 → PROX_LEFT_T2 → TURN_RIGHT | Recruit the mirrored right turn |

The scene pathway has one Theta OPU. Each proximity pathway has two Theta
OPUs. Adding a second Theta to the camera pathway changes this circuit.

| Populations | Rhythm | TNorm |
| --- | --- | --- |
| CAMERA_RELAY, PROX_RIGHT_RELAY, PROX_LEFT_RELAY | high-gamma | 10 |
| CAMERA_SCENE, PROX_RIGHT_T1, PROX_LEFT_T1 | theta | 3 |
| PROX_RIGHT_T2, PROX_LEFT_T2 | theta | 2.01 |
| FORWARD_LEFT, FORWARD_RIGHT, TURN_LEFT, TURN_RIGHT | beta | 5 |

These are the operating points of this public design. The SDK submits the
design for compilation; the application supplies measurements and applies the
returned output states.

## Connect the action relationships

| Source | Inhibitory targets | Relationship |
| --- | --- | --- |
| TURN_LEFT | TURN_RIGHT | Competition between turns |
| TURN_RIGHT | TURN_LEFT | Competition between turns |
| TURN_LEFT | FORWARD_LEFT and WHEEL_LEFT | Suppress the left motor pathway and clear its held output |
| TURN_RIGHT | FORWARD_RIGHT and WHEEL_RIGHT | Suppress the right motor pathway and clear its held output |

All six inhibitory connections use 100% of the compiler's reference strength.
That percentage is a strength setting, not a guaranteed percentage of suppressed
neurons. There are no extra self-reset branches in the avoidance circuit.

## Acknowledge each observation

The separate transport path is TRANSPORT_ACK → TRANSPORT_ACK_RELAY →
TRANSPORT_ACK_OUT. The output excites TRANSPORT_ACK_CLEAR, which inhibits the
ACK output and itself. Both relays use high-gamma T10. The controller observes
the output clearing before sending the next pulse.

At a fresh ACK, the controller immediately uses the wheel states from that same
output frame and advances Webots by `physics_step_ms` (32 ms by default).
It waits for ACK to
clear before publishing the next observation. There is no post-ACK readout delay.
An HTTP queue receipt or ordinary wheel activity cannot complete this sequence.
See [ACK.md](ACK.md) for the complete exchange and failure behavior.

When the right wheel advances while the left wheel is stopped, this body turns
left. The opposite output combination produces a right turn. The controller
does not compare proximity readings or choose which turn should win.

## Define and extend the goal

The goal is to maintain movement while changing direction in response to
front obstacles. Continuing scene activity supports forward movement. A turn
pathway opposes a particular forward action and competes with the other turn.

To add another goal, identify the actions it supports and the situations where
those actions conflict with avoidance. Connect its evidence to the relevant
action pathways, then observe suppression, release and recovery. Use the worked
conflict exercise in [GOALS.md](GOALS.md).

The blue and green floor markers do not enter the graph as start or target
coordinates. This primitive does not implement maze planning or destination
recognition. Validate the compiled design in the supplied world using
[VALIDATION.md](VALIDATION.md).
