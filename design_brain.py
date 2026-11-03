"""Primitive A: front avoidance with competing turn pathways."""
from pathlib import Path
from ab import Brain

ROOT = Path(__file__).resolve().parent


def proximity_path(brain, name, width):
    brain.input(name, width)
    brain.opu(name + "_RELAY", "high-gamma", 10)
    brain.opu(name + "_T1", "theta", 3)
    brain.opu(name + "_T2", "theta", 2.01)
    brain.connect(name, name + "_RELAY")
    brain.connect(name + "_RELAY", name + "_T1")
    brain.connect(name + "_T1", name + "_T2")
    return name + "_T2"


def create_brain():
    brain = Brain("Primitive A")
    # The scene pathway has ONE Theta population. The two-stage sensory
    # decision construction below belongs to the proximity pathways.
    brain.input("CAMERA", 64)
    brain.opu("CAMERA_RELAY", "high-gamma", 10)
    brain.opu("CAMERA_SCENE", "theta", 3)
    brain.connect("CAMERA", "CAMERA_RELAY")
    brain.connect("CAMERA_RELAY", "CAMERA_SCENE")
    right = proximity_path(brain, "PROX_RIGHT", 16)
    left = proximity_path(brain, "PROX_LEFT", 16)

    # Camera activity supplies the forward drive in this particular example.
    # A dark image is not replaced with a fabricated tonic input.
    for side in ("LEFT", "RIGHT"):
        brain.opu("FORWARD_" + side, "beta", 5)
        brain.output("WHEEL_" + side)
        brain.connect("CAMERA_SCENE", "FORWARD_" + side)
        brain.connect("FORWARD_" + side, "WHEEL_" + side)

    brain.opu("TURN_LEFT", "beta", 5)
    brain.opu("TURN_RIGHT", "beta", 5)
    brain.connect(right, "TURN_LEFT")
    brain.connect(left, "TURN_RIGHT")

    # Competing turn pathways oppose each other inside the brain.
    brain.connect("TURN_LEFT", "TURN_RIGHT", "inh")
    brain.connect("TURN_RIGHT", "TURN_LEFT", "inh")
    for side in ("LEFT", "RIGHT"):
        # Slowing the left wheel while the right moves produces a left turn.
        # Suppress its motor population AND clear its held bistable output.
        brain.connect("TURN_" + side, "FORWARD_" + side, "inh")
        brain.connect("TURN_" + side, "WHEEL_" + side, "inh")

    # Isolated transport acknowledgement. Feedback clears the held output
    # and its clearing relay before the next observation is sent.
    brain.input("TRANSPORT_ACK", 1)
    brain.opu("TRANSPORT_ACK_RELAY", "high-gamma", 10)
    brain.output("TRANSPORT_ACK_OUT")
    brain.opu("TRANSPORT_ACK_CLEAR", "high-gamma", 10)
    brain.connect("TRANSPORT_ACK", "TRANSPORT_ACK_RELAY")
    brain.connect("TRANSPORT_ACK_RELAY", "TRANSPORT_ACK_OUT")
    brain.connect("TRANSPORT_ACK_OUT", "TRANSPORT_ACK_CLEAR")
    brain.connect("TRANSPORT_ACK_CLEAR", "TRANSPORT_ACK_OUT", "inh")
    brain.connect("TRANSPORT_ACK_CLEAR", "TRANSPORT_ACK_CLEAR", "inh", role="feedback")
    # Arrange the same public graph for inspection in ab design.
    positions = {
        "CAMERA": (40, 400), "CAMERA_RELAY": (300, 400),
        "CAMERA_SCENE": (560, 400),
        "FORWARD_LEFT": (1340, 290), "WHEEL_LEFT": (1600, 290),
        "FORWARD_RIGHT": (1340, 550), "WHEEL_RIGHT": (1600, 550),
        "TURN_LEFT": (1080, 60), "TURN_RIGHT": (1080, 780),
        "TRANSPORT_ACK": (40, 1100), "TRANSPORT_ACK_RELAY": (300, 1100),
        "TRANSPORT_ACK_OUT": (560, 1100), "TRANSPORT_ACK_CLEAR": (820, 1100),
    }
    for name, y in (("PROX_RIGHT", 60), ("PROX_LEFT", 780)):
        for suffix, x in (("", 40), ("_RELAY", 300), ("_T1", 560), ("_T2", 820)):
            positions[name + suffix] = (x, y)
    design = brain.to_dict()
    for node in design["nodes"]:
        node["x"], node["y"] = positions[node["name"]]
    return Brain.from_dict(design)


def main():
    brain = create_brain()
    brain.save(ROOT / "brain.abdesign.json")
    print("Saved brain.abdesign.json. Compile it on Prima-Lux before running.")


if __name__ == "__main__":
    main()
