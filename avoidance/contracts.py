"""Named public populations shared by the robot and transport adapters."""
ACK_INPUT = "TRANSPORT_ACK"
ACK_OUTPUT = "TRANSPORT_ACK_OUT"
WHEEL_OUTPUTS = ("WHEEL_LEFT", "WHEEL_RIGHT")
INPUT_SIZES = {"CAMERA": 64, "PROX_LEFT": 16, "PROX_RIGHT": 16, ACK_INPUT: 1}
OUTPUT_SIZES = {name: 1 for name in (*WHEEL_OUTPUTS, ACK_OUTPUT)}
