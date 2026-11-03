# Teaching project sequence

Each project should teach a construction that a developer can reuse in another
body. This is the proposed sequence for the series; this repository implements
the first lesson.

| Project | Environment | Main lesson | What a developer changes |
| --- | --- | --- | --- |
| Front obstacle avoidance | Webots | Sensory input primitive and its influence on movement | Sensory pathways and turn-to-wheel relationships |
| Seven-joint arm | Webots | Opposing motor primitives and coordinated joint movement | Targets, body mapping and joint primitives |
| Combined open field | Webots | Connecting goals through support, competition and veto | Individual goals, combined goals and their conflict relationships |
| Object-seeking ant | Physical robot | Perception evidence, search, approach and avoidance | Target descriptions, sensing and goal interactions |
| Taught-pose SO101 | Physical arm | Developer-selected goals in a real body | Record poses on the actual arm and choose their sequence |

The arm lesson must identify which parts generate references, calculate errors,
move through a sequence, and drive the motors. Conventional IK target generation
must remain distinct from neural motor execution when it is used.

The ant lesson must distinguish the external vision-language model's evidence
from the actions chosen by the neural circuit. Its hardware guide should include
the exact components, wiring, firmware, host dependencies and model setup.

The SO101 lesson must teach users to record their own starting and target poses.
Saved raw encoder positions from another robot are not universal positions.

Every project's README should provide: requirements; clone, build and run;
expected observations; input/output meanings; the neural construction; how to
build its goal; how its goals interact; exercises; and the scope of validation.
