import math
from rover_interfaces.msg import ArmStatus, SensorReadings
from .protocol import AXES, SENSOR_FIELDS, is_number


STATUS_FIELDS = (
    "ready", "enabled", "mode", "bridge_mode", "operator_online", "pico_online",
    "note", "error", "motor_ready", "motor_speed", "motor_limit", "imu_ready",
    "bmp_ready", "sd_ready", "sd_rows", "sd_file", "sensor_error", "sd_error",
)
SENSOR_NAMES = {
    "temperature": "temperature_c", "pressure": "pressure_kpa",
    "accel_x": "accel_x", "accel_y": "accel_y", "accel_z": "accel_z",
    "altitude": "altitude_m",
}


def status_message(data):
    # The Pico sends JSON; ROS uses ArmStatus.
    msg = ArmStatus()
    for name in STATUS_FIELDS:
        if name not in data:
            continue
        value = data[name]
        default = getattr(msg, name)
        if isinstance(default, float):
            if not is_number(value):
                raise ValueError("Invalid numeric status: " + name)
            value = float(value)
        elif isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError("Invalid boolean status: " + name)
        elif isinstance(default, str):
            if not isinstance(value, str):
                raise ValueError("Invalid text status: " + name)
        elif name == "sd_rows" and (type(value) is not int or not 0 <= value <= 0xFFFFFFFF):
            raise ValueError("Invalid SD row count")
        setattr(msg, name, value)
    names, targets, minimums, maximums = [], [], [], []
    for joint in AXES:
        if joint not in data.get("targets", {}) or joint not in data.get("limits", {}):
            continue
        angle = data["targets"][joint]
        low, high = data["limits"][joint]
        if not all(is_number(value) for value in (angle, low, high)):
            raise ValueError("Invalid joint status")
        names.append(joint)
        targets.append(float(angle))
        minimums.append(float(low))
        maximums.append(float(high))
    msg.joint_names, msg.target_deg = names, targets
    msg.min_deg, msg.max_deg = minimums, maximums
    status_data(msg)
    return msg


def status_data(msg):
    arrays = (msg.joint_names, msg.target_deg, msg.min_deg, msg.max_deg)
    if len({len(values) for values in arrays}) != 1:
        raise ValueError("Status arrays must have the same length")
    if len(set(msg.joint_names)) != len(msg.joint_names):
        raise ValueError("Repeated joint in status")
    if not all(name in AXES for name in msg.joint_names):
        raise ValueError("Unknown joint in status")
    values = list(msg.target_deg) + list(msg.min_deg) + list(msg.max_deg)
    values += [msg.motor_speed, msg.motor_limit, msg.sd_rows]
    if not all(is_number(value) for value in values):
        raise ValueError("Status values must be finite")
    if msg.ready and any(low >= high for low, high in zip(msg.min_deg, msg.max_deg)):
        raise ValueError("Invalid joint limits")
    data = {name: getattr(msg, name) for name in STATUS_FIELDS}
    data["targets"] = dict(zip(msg.joint_names, msg.target_deg))
    data["limits"] = {name: [low, high] for name, low, high in
                      zip(msg.joint_names, msg.min_deg, msg.max_deg)}
    return data


def sensor_message(packet):
    msg = SensorReadings()
    msg.simulated = packet["mode"] == "simulation"
    msg.elapsed_ms = int(packet.get("elapsed_ms", 0))
    for field in SENSOR_FIELDS:
        value = packet["data"].get(field)
        setattr(msg, SENSOR_NAMES[field], float(value) if value is not None else math.nan)
    return msg


def sensor_data(msg):
    data = {}
    for name, ros_name in SENSOR_NAMES.items():
        value = getattr(msg, ros_name)
        if math.isinf(value):
            raise ValueError("Infinite sensor reading")
        data[name] = value if math.isfinite(value) else None
    return {"type": "sensors", "mode": "simulation" if msg.simulated else "hardware",
            "elapsed_ms": msg.elapsed_ms, "data": data}
