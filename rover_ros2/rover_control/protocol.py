# Shared command and sensor messages.
AXES = ("Base", "Shoulder", "Elbow", "Wrist", "Gripper")
CONTROL_COMMANDS = ("ARM_ENABLE", "STOP_ALL", "HEARTBEAT", "STATUS", "LINK_LOST")
SENSOR_FIELDS = ("temperature", "pressure", "accel_x", "accel_y", "accel_z", "altitude")

def is_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and value == value and value not in (float("inf"), float("-inf")))

def validate_command(request):
    if isinstance(request, str):
        request = {"command": request}
    if not isinstance(request, dict):
        raise ValueError("Command must be an object")
    if set(request) == {"command"}:
        if request["command"] not in CONTROL_COMMANDS:
            raise ValueError("Unknown control command")
        return dict(request)
    if set(request) == {"motor", "speed"}:
        if request["motor"] != "DC" or not is_number(request["speed"]):
            raise ValueError("Motor command needs DC and a finite speed")
        if not -100 <= request["speed"] <= 100:
            raise ValueError("Motor speed must be between -100 and 100 percent")
        return {"motor": "DC", "speed": request["speed"]}
    if set(request) != {"axis", "angle"}:
        raise ValueError("Servo command needs axis and angle")
    if not isinstance(request["axis"], str):
        raise ValueError("Axis must be a name")
    axis = request["axis"].title()
    if axis not in AXES:
        raise ValueError("Unknown axis: " + axis)
    if not is_number(request["angle"]):
        raise ValueError("Angle must be a finite number")
    return {"axis": axis, "angle": request["angle"]}

def valid_sensor_packet(packet):
    return (isinstance(packet, dict) and packet.get("type") == "sensors"
            and packet.get("mode") in ("hardware", "simulation")
            and isinstance(packet.get("data"), dict)
            and any(key in packet["data"] for key in SENSOR_FIELDS)
            and all(value is None or is_number(value)
                    for key, value in packet["data"].items() if key in SENSOR_FIELDS))
