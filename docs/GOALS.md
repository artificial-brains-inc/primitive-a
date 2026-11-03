# Building and connecting goals

A goal describes a condition you want the body to maintain or reach. A primitive
provides a useful operation or behavior. Build the goal by connecting the
observations, comparisons and actions that make progress toward that condition.

## 1. Describe an observable result

For front avoidance: movement should change when a front obstacle comes into
range, and forward movement should be able to return after the robot turns away.
This is a continuous objective, so there is no final DONE output in this design.

For reaching: a selected body position should approach a target. If completion
needs an explicit signal, build the corresponding condition. Silence in two
opposing pathways can also mean missing evidence; it is not automatically success.

## 2. List observations, references and actions

Keep these distinct:

| Item | Meaning | Example |
| --- | --- | --- |
| Observation | What the body or sensor currently measures | Proximity, measured joint position, target evidence from a detector |
| Reference | A desired value or an explicit default state | Desired joint position or active run reference |
| Neural condition | A result formed from incoming evidence | A directional difference or obstacle-related activity |
| Candidate action | Something the body can do | Turn left, flex a joint, extend a joint |
| Output lifetime | How long a selected command persists and how it ends | Hold until inhibited, or clear through a reset branch |

This project uses three observations: CAMERA, PROX_LEFT and PROX_RIGHT. It has
no separate adjustable target reference. The forward/avoid relationship is
encoded in its connections.

TRANSPORT_ACK is an additional synchronization input. Its isolated circuit
confirms receipt before the controller reads the decision and advances the
body. It does not supply a goal, obstacle measurement or motor preference.

The sensor adapter scales raw proximity into 16 cumulative input values. That
encoding represents the measurement; it does not select a wheel or calculate
a turn command. The camera supplies a fixed 8 by 8 grayscale sample.

## 3. Build one useful path first

Each proximity pathway is high-gamma T10 to Theta T3 to Theta T2.01 to Beta T5.
The Beta result participates in an action relationship. The camera pathway
has a different role: CAMERA_RELAY feeds one CAMERA_SCENE Theta T3 population,
which excites both forward Beta T5 populations.

For PROX_RIGHT, follow PROX_RIGHT_RELAY, PROX_RIGHT_T1, PROX_RIGHT_T2, TURN_LEFT,
FORWARD_LEFT and WHEEL_LEFT. Observe whether changing that measurement changes
the intended neural path and then the body. Repeat for the mirrored side.

TNorm selects an operating point. It is not a priority number, a sensor value,
a fuzzy truth degree or a wheel gain. Keep 2.01 exact when using this recipe.

## 4. Decide relationships where actions meet

For every pair of goals, ask:

1. Can an action help both? Allow compatible evidence to support it.
2. Does evidence oppose an action while leaving room for other support? Use contradiction.
3. Must a specific action be suppressed? Build a veto and observe that it works.
4. Are two body actions incompatible? Add competition between the relevant pathways.
5. Can actions run together? Preserve that cooperation.
6. Does the next action require a completed state? Provide an observed transition condition.

Do this at the appropriate scope. Opposing movements at one joint may compete;
shoulder and elbow do not have to suppress each other. A nearby obstacle may
oppose approach without erasing the target evidence that made approach useful.

## 5. Work through a light-approach extension

The following is a design exercise for the next project. It is not an implemented
light detector or a claim about this project's behavior.

| Situation | Approach goal | Avoidance goal | Relationship to design |
| --- | --- | --- | --- |
| Target right; right side clear | Supports turning right | No right-side obstacle evidence | Allow the approach pathway to influence the right turn. |
| Target right; obstacle right | Supports turning right | Supports turning left | Define which approach pathway the obstacle veto suppresses. |
| Target left; obstacle right | Supports turning left | Supports turning left | Both can support a compatible movement; preserve source compatibility. |
| No target evidence | Provides no positive approach evidence | Still responds to obstacles | Search requires its own active reference/default mechanism. |
| Obstacle leaves range | Target may still support approach | Obstacle evidence changes | Verify veto release, output clearing and renewed approach. |

Represent the selected target through actual perception. An external model can
provide visual evidence, but document what that model computes and what the
neural circuit decides. Target absence does not become a positive SEARCH
command by itself.

When a calculation needs several operands, follow the guide's common-rhythm
representations and explicit operand units, including positive terms. A veto
serves a different purpose from arithmetic subtraction. Do not increase an
arithmetic operand's inhibition and describe the result as the same calculation.

## 6. Give outputs a lifetime

The wheel outputs are bistable. In this design, a turn pathway both inhibits
the relevant FORWARD population and clears the corresponding WHEEL output.
These are separate jobs. The continuing camera pathway can excite forward
movement again when the circuit permits it.

No self-reset is included in this lesson's motor pathways. If a new primitive
must reconsider its evidence after an action, the guide describes Beta T5 to
a separate reset Beta T3, with inhibitory returns to Theta T2.01 and the output.
Adding that branch changes the circuit and requires observing its new timing.

## 7. Test interactions, not only individual goals

Test each goal alone, then together. Include agreement, direct conflict,
symmetry, evidence appearing and disappearing, and return to the earlier goal.
Read the sensory activity, candidate populations, output state and physical
movement together. A correct-looking diagram does not establish that all of
those transitions work on a device.

The [public guide](https://github.com/artificial-brains-inc/Guide-to-Building-an-Artificial-Brain)
provides the construction rules. Chapters 6–11 cover connections, useful
operating points, comparisons and decisions; chapter 13 covers motor output
clearing and interaction.
