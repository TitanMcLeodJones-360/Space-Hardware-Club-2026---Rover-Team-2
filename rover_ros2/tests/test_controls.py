from collections import deque
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rover_control.rover_arm import RoverArm
from rover_control import protocol


class ArmTests(unittest.TestCase):
    def setUp(self):
        self.arm = RoverArm(dry_run=True)
        self.arm.setup_servos()

    def test_starts_stopped(self):
        status = self.arm.handle_command({"axis": "Axis1", "angle": 95})
        self.assertFalse(status["enabled"])
        self.assertEqual(status["targets"]["Axis1"], 90)
        self.assertIn("error", status)

    def test_joint_commands(self):
        self.arm.handle_command("ARM_ENABLE")
        for name in ("AXIS1", "AXIS2", "AXIS3A", "AXIS3B"):
            self.arm.handle_command({"axis": name, "angle": 95})
            self.assertEqual(self.arm.angles[name.title()], 70 if name == "AXIS3A" else 95)
            self.arm.handle_command({"axis": name, "angle": 90})
            self.assertEqual(self.arm.angles[name.title()], 70 if name == "AXIS3A" else 90)

    def test_gripper(self):
        self.arm.handle_command("ARM_ENABLE")
        self.arm.handle_command({"axis": "Axis3B", "angle": 120})
        self.assertEqual(self.arm.angles["Axis3B"], 120)
        self.arm.handle_command({"axis": "Axis3B", "angle": 60})
        self.assertEqual(self.arm.angles["Axis3B"], 60)

    def test_preview_limits(self):
        self.arm.handle_command("ARM_ENABLE")
        self.arm.handle_command({"axis": "Axis1", "angle": 300})
        self.assertEqual(self.arm.angles["Axis1"], 180)
        self.arm.handle_command({"axis": "Axis1", "angle": -30})
        self.assertEqual(self.arm.angles["Axis1"], 0)

    def test_duplicate_angle_is_idempotent(self):
        self.arm.handle_command("ARM_ENABLE")
        for _ in range(4):
            self.arm.handle_command({"axis": "Axis1", "angle": 95})
        self.assertEqual(self.arm.angles["Axis1"], 95)

    def test_invalid_angle_rejected(self):
        for value in (True, float("nan"), float("inf"), "95"):
            self.assertIn("error", self.arm.handle_command({"axis": "Axis1", "angle": value}))

    def test_stop_requires_enable(self):
        self.arm.handle_command("ARM_ENABLE")
        self.arm.handle_command({"axis": "Axis1", "angle": 95})
        self.arm.handle_command("STOP_ALL")
        self.arm.handle_command({"axis": "Axis1", "angle": 100})
        self.assertEqual(self.arm.angles["Axis1"], 95)
        self.arm.handle_command("HEARTBEAT")
        self.assertFalse(self.arm.enabled)
        self.arm.handle_command("ARM_ENABLE")
        self.arm.handle_command({"axis": "Axis1", "angle": 100})
        self.assertEqual(self.arm.angles["Axis1"], 100)

    def test_link_loss(self):
        self.arm.handle_command("ARM_ENABLE")
        self.arm.handle_command("LINK_LOST")
        self.assertFalse(self.arm.enabled)

    def test_bad_command_stops_arm(self):
        self.arm.handle_command("ARM_ENABLE")
        for command in ("BAD", "DRIVE_FORWARD", "BASE_OTHER"):
            self.assertIn("error", self.arm.handle_command(command))
            self.assertFalse(self.arm.enabled)

    def test_unconfigured_hardware_rejected(self):
        with self.assertRaises(ValueError):
            RoverArm(dry_run=False).setup_servos()

    def test_motor_rejects_motion_until_enabled(self):
        result = self.arm.handle_command({"motor": "DC", "speed": 15})
        self.assertIn("error", result)
        self.assertEqual(self.arm.motor_speed, 0)

    def test_motor_limits_and_stop(self):
        self.arm.handle_command("ARM_ENABLE")
        self.arm.handle_command({"motor": "DC", "speed": 100})
        self.assertEqual(self.arm.motor_speed, 30)
        self.arm.handle_command({"motor": "DC", "speed": -15})
        self.assertEqual(self.arm.motor_speed, -15)
        self.arm.handle_command("STOP_ALL")
        self.assertEqual(self.arm.motor_speed, 0)
        self.assertFalse(self.arm.enabled)

    def test_bad_motor_values_stop_outputs(self):
        for value in (True, float("nan"), float("inf"), "15", 101, -101):
            self.arm.handle_command("ARM_ENABLE")
            result = self.arm.handle_command({"motor": "DC", "speed": value})
            self.assertIn("error", result)
            self.assertFalse(self.arm.enabled)


# These doubles test our node logic. They do not emulate DDS discovery or ROS scheduling.
class Message:
    def __init__(self):
        self.data = None


class Publisher:
    def __init__(self):
        self.messages = []
    def publish(self, message):
        self.messages.append(message)


class FakeNode:
    overrides = {}
    def __init__(self, name):
        self.parameters = {}
    def declare_parameter(self, name, default):
        self.parameters[name] = self.overrides.get(name, default)
    def get_parameter(self, name):
        return types.SimpleNamespace(value=self.parameters[name])
    def create_publisher(self, *args):
        return Publisher()
    def create_subscription(self, *args):
        return args[2]
    def create_timer(self, interval, callback):
        return callback
    def get_logger(self):
        return types.SimpleNamespace(info=lambda value: None, error=lambda value: None,
                                     warning=lambda value: None)
    def destroy_node(self):
        pass


def interface_double(name):
    # Match the field names/defaults, but this does not test ROS-generated code.
    definition = ROOT.parent / "rover_interfaces" / "msg" / (name + ".msg")
    fields = {}
    for line in definition.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            kind, field = line.split()
            fields[field] = kind

    class Interface:
        def __init__(self):
            for field, kind in fields.items():
                value = [] if kind.endswith("[]") else {"bool": False, "string": "",
                         "uint32": 0, "float64": 0.0}[kind]
                setattr(self, field, value)

        def __setattr__(self, field, value):
            # float64 setters require floats in the generated Python messages.
            if fields.get(field) == "float64" and type(value) is not float:
                raise AssertionError("Expected float for " + field)
            object.__setattr__(self, field, value)

    return Interface


def fake_ros_modules():
    ros = types.ModuleType("rclpy")
    ros.spin_once = lambda *args, **kwargs: None
    node = types.ModuleType("rclpy.node")
    node.Node = FakeNode
    qos = types.ModuleType("rclpy.qos")
    qos.QoSProfile = lambda **kwargs: kwargs
    qos.ReliabilityPolicy = types.SimpleNamespace(RELIABLE=1)
    qos.DurabilityPolicy = types.SimpleNamespace(VOLATILE=1)
    msgs = types.ModuleType("std_msgs.msg")
    msgs.Bool = msgs.Empty = msgs.Float32 = Message
    sensor_msgs = types.ModuleType("sensor_msgs.msg")
    sensor_msgs.Joy = Message
    interfaces = types.ModuleType("rover_interfaces.msg")
    for name in ("JointCommand", "ArmStatus", "SensorReadings"):
        setattr(interfaces, name, interface_double(name))
    return {"rclpy": ros, "rclpy.node": node, "rclpy.qos": qos,
            "std_msgs": types.ModuleType("std_msgs"), "std_msgs.msg": msgs,
            "sensor_msgs": types.ModuleType("sensor_msgs"), "sensor_msgs.msg": sensor_msgs,
            "rover_interfaces": types.ModuleType("rover_interfaces"),
            "rover_interfaces.msg": interfaces}


class FakeSerial:
    def __init__(self):
        self.incoming = b""
        self.writes = []
        self.closed = False
    @property
    def in_waiting(self):
        return len(self.incoming)
    def read(self, count):
        result, self.incoming = self.incoming[:count], self.incoming[count:]
        return result
    def write(self, frame):
        self.writes.append(frame)
        return len(frame)
    def reset_input_buffer(self):
        self.incoming = b""
    def close(self):
        self.closed = True


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = patch.dict(sys.modules, fake_ros_modules())
        cls.modules.start()
        cls.bridge_module = importlib.import_module("rover_control.arm_bridge")
        cls.gui_ros_module = importlib.import_module("rover_control.ground_station_ros")
        cls.messages = importlib.import_module("rover_control.ros_messages")

    @classmethod
    def tearDownClass(cls):
        cls.modules.stop()

    def setUp(self):
        self.now = 10.0
        self.clock = patch("time.monotonic", lambda: self.now)
        self.clock.start()
        FakeNode.overrides = {}
        self.bridge = self.bridge_module.ArmBridge()

    def tearDown(self):
        self.clock.stop()
        FakeNode.overrides = {}

    def message(self, data):
        msg = Message()
        msg.data = data
        return msg

    def joint(self, angle=95):
        return types.SimpleNamespace(joint="Axis1", angle_deg=angle)

    def start_arm(self):
        self.bridge.receive_heartbeat(self.message(True))
        self.bridge.receive_enable(self.message(True))

    def serial_bridge(self):
        serial = FakeSerial()
        FakeNode.overrides = {"dry_run": False, "serial_port": "/dev/test"}
        with patch.dict(sys.modules, serial=types.SimpleNamespace(Serial=lambda *a, **k: serial)):
            bridge = self.bridge_module.ArmBridge()
        return bridge, serial

    def test_gui_to_bridge_round_trip(self):
        statuses = []
        gui = self.gui_ros_module.GroundStationROS(statuses.append)
        self.bridge.publish_status()
        gui.receive_status(self.bridge.publisher.messages[-1])
        gui.send_heartbeat()
        self.bridge.receive_heartbeat(gui.heartbeat.messages[-1])
        gui.send_command("ARM_ENABLE")
        self.bridge.receive_enable(gui.enable_publisher.messages[-1])
        gui.send_command({"axis": "Axis1", "angle": 95})
        joint = gui.joint_publisher.messages[-1]
        self.assertEqual((joint.joint, joint.angle_deg), ("Axis1", 95.0))
        self.bridge.receive_joint(joint)
        self.bridge.publish_status()
        gui.receive_status(self.bridge.publisher.messages[-1])
        self.assertEqual(statuses[-1]["targets"]["Axis1"], 95)
        self.assertEqual(statuses[-1]["bridge_mode"], "simulation")

    def test_bridge_rejects_enable_without_heartbeat(self):
        self.bridge.receive_enable(self.message(True))
        self.assertFalse(self.bridge.arm.enabled)
        self.assertTrue(self.bridge.publisher.messages[-1].error)

    def test_gui_disconnect_stops_simulation(self):
        self.start_arm()
        self.now += 0.9
        self.bridge.poll()
        self.assertFalse(self.bridge.arm.enabled)
        self.bridge.receive_heartbeat(self.message(True))
        self.assertFalse(self.bridge.arm.enabled)

    def test_late_heartbeat_stops_before_reconnection(self):
        self.start_arm()
        self.now += 0.9
        self.bridge.receive_heartbeat(self.message(True))
        self.assertFalse(self.bridge.arm.enabled)

    def test_motor_refresh_timeout_stops_only_motor(self):
        self.start_arm()
        self.bridge.receive_motor(self.message(15.0))
        self.now += 0.31
        self.bridge.poll()
        self.assertEqual(self.bridge.arm.motor_speed, 0)
        self.assertTrue(self.bridge.arm.enabled)

    def test_motor_zero_is_allowed_without_connection(self):
        bridge, serial = self.serial_bridge()
        bridge.receive_motor(self.message(0.0))
        self.assertEqual(json.loads(serial.writes[-1]), {"motor": "DC", "speed": 0})
        gui = self.gui_ros_module.GroundStationROS(Mock())
        gui.send_command({"motor": "DC", "speed": 0})
        self.assertEqual(gui.motor_publisher.messages[-1].data, 0.0)

    def test_stop_topic_and_enable_false_stop(self):
        self.start_arm()
        self.bridge.receive_motor(self.message(15.0))
        self.bridge.receive_stop(Message())
        self.assertFalse(self.bridge.arm.enabled)
        self.assertEqual(self.bridge.arm.motor_speed, 0)
        self.start_arm()
        self.bridge.receive_enable(self.message(False))
        self.assertFalse(self.bridge.arm.enabled)

    def test_gui_ignores_mismatched_status_arrays(self):
        gui = self.gui_ros_module.GroundStationROS(Mock())
        msg = self.messages.status_message(self.bridge.status_data)
        msg.target_deg = []
        gui.receive_status(msg)
        self.assertIsNone(gui.last_status)

    def test_gui_ignores_nonfinite_targets(self):
        gui = self.gui_ros_module.GroundStationROS(Mock())
        msg = self.messages.status_message(self.bridge.status_data)
        msg.target_deg[0] = float("nan")
        gui.receive_status(msg)
        self.assertIsNone(gui.last_status)

    def test_gui_blocks_stale_status(self):
        gui = self.gui_ros_module.GroundStationROS(Mock())
        self.bridge.publish_status()
        gui.receive_status(self.bridge.publisher.messages[-1])
        self.now += 2
        with self.assertRaises(ValueError):
            gui.send_command({"axis": "Axis1", "angle": 95})
        gui.send_command("STOP_ALL")
        self.assertEqual(len(gui.stop_publisher.messages), 1)

    def test_serial_requires_pico_reply(self):
        bridge, serial = self.serial_bridge()
        bridge.receive_heartbeat(self.message(True))
        bridge.receive_enable(self.message(True))
        self.assertNotIn({"command": "ARM_ENABLE"}, [json.loads(frame) for frame in serial.writes])
        serial.incoming = b'{"mode":"simulation","ready":true,"enabled":false}\n'
        bridge.poll()
        bridge.receive_enable(self.message(True))
        self.assertIn({"command": "ARM_ENABLE"}, [json.loads(frame) for frame in serial.writes])

    def test_fragmented_and_bad_serial(self):
        bridge, serial = self.serial_bridge()
        serial.incoming = b'not json\n{"mode":"hardware","ready":true,'
        bridge.poll()
        self.assertIsNone(bridge.last_pico_status)
        serial.incoming = b'"enabled":false}\n'
        bridge.poll()
        self.assertTrue(bridge.pico_online())
        self.now += 1.1
        bridge.publish_status()
        self.assertFalse(bridge.publisher.messages[-1].ready)

    def test_sensor_data_reaches_ground_station(self):
        bridge, serial = self.serial_bridge()
        packets = []
        gui = self.gui_ros_module.GroundStationROS(Mock(), packets.append)
        packet = {"type": "sensors", "mode": "hardware", "elapsed_ms": 123,
                  "data": {"temperature": 24.5, "pressure": 101.2, "accel_x": 0.1}}
        serial.incoming = (json.dumps(packet) + "\n").encode()
        bridge.poll()
        gui.receive_sensors(bridge.sensor_publisher.messages[-1])
        self.assertEqual(packets[0]["data"]["temperature"], 24.5)
        self.assertIsNone(packets[0]["data"]["altitude"])
        self.assertEqual(packets[0]["elapsed_ms"], 123)
        self.assertIsNotNone(gui.last_sensors)
        self.assertIsNone(bridge.last_pico_status)

    def test_bad_sensor_packet_is_not_published(self):
        bridge, serial = self.serial_bridge()
        for data in ({"temperature": "bad"}, {"temperature": float("nan")}, {}):
            serial.incoming = (json.dumps({"type": "sensors", "mode": "hardware", "data": data}) + "\n").encode()
            bridge.poll()
        self.assertEqual(bridge.sensor_publisher.messages, [])

    def test_integer_json_status_becomes_float_fields(self):
        msg = self.messages.status_message(self.bridge.status_data)
        self.assertIs(type(msg.motor_speed), float)
        self.assertIs(type(msg.motor_limit), float)
        self.assertTrue(all(type(v) is float for v in msg.target_deg))

    def test_invalid_pico_status_does_not_refresh_connection(self):
        bridge, serial = self.serial_bridge()
        for field, value in (("motor_speed", "bad"), ("sd_rows", -1), ("note", 5)):
            packet = {"mode": "hardware", "ready": True, "enabled": False, field: value}
            serial.incoming = (json.dumps(packet) + "\n").encode()
            bridge.poll()
        self.assertIsNone(bridge.last_pico_status)
        self.assertIsNotNone(bridge.serial)

    def test_joint_and_motor_callbacks_write_pico_commands(self):
        bridge, serial = self.serial_bridge()
        bridge.receive_heartbeat(self.message(True))
        serial.incoming = b'{"mode":"simulation","ready":true,"enabled":false}\n'
        bridge.poll()
        bridge.receive_joint(self.joint())
        self.assertEqual(json.loads(serial.writes[-1]), {"axis": "Axis1", "angle": 95})
        bridge.receive_motor(self.message(-15.0))
        self.assertEqual(json.loads(serial.writes[-1]), {"motor": "DC", "speed": -15})

    def test_short_serial_write_marks_disconnect(self):
        bridge, serial = self.serial_bridge()
        serial.write = lambda frame: 0
        bridge.write_command("STATUS")
        self.assertIsNone(bridge.serial)
        self.assertTrue(serial.closed)


class GUIActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No Qt display here; exercise the actual callbacks with widget doubles.
        widgets = types.ModuleType("PyQt5.QtWidgets")
        for name in ("QApplication", "QMainWindow", "QWidget", "QLabel", "QPushButton",
                     "QTextEdit", "QGroupBox", "QGridLayout", "QVBoxLayout", "QHBoxLayout",
                     "QDoubleSpinBox"):
            setattr(widgets, name, object)
        qtcore = types.ModuleType("PyQt5.QtCore")
        qtcore.QTimer = object
        modules = {"PyQt5": types.ModuleType("PyQt5"), "PyQt5.QtWidgets": widgets,
                   "PyQt5.QtCore": qtcore, "pyqtgraph": types.ModuleType("pyqtgraph")}
        with patch.dict(sys.modules, modules):
            cls.gui_module = importlib.import_module("rover_control.ground_station")

    def test_plus_button_publishes_axis_and_angle(self):
        window = self.gui_module.GroundStation.__new__(self.gui_module.GroundStation)
        window.demo = False
        window.log = Mock()
        window.ros = types.SimpleNamespace(send_command=Mock())
        target = [90]
        window.angle_inputs = {"Axis1": types.SimpleNamespace(
            value=lambda: target[0], setValue=lambda value: target.__setitem__(0, value))}
        window.change_target("Axis1", 5)
        window.ros.send_command.assert_called_once_with({"axis": "Axis1", "angle": 95})

    def test_held_motor_sends_refresh_and_release_sends_zero(self):
        window = self.gui_module.GroundStation.__new__(self.gui_module.GroundStation)
        window.demo = False
        window.ros = types.SimpleNamespace(connected=lambda: True)
        window.last_arm_status = {"enabled": True, "motor_ready": True}
        window.motor_input = types.SimpleNamespace(value=lambda: 15)
        window.motor_timer = Mock()
        window.send_command = Mock()
        window.start_motor(-1)
        window.refresh_motor()
        self.assertEqual(window.send_command.call_args.args[0], {"motor": "DC", "speed": -15})
        window.stop_motor()
        window.send_command.assert_called_with({"motor": "DC", "speed": 0})
        self.assertEqual(window.motor_direction, 0)
        window.motor_timer.stop.assert_called_once()

    def test_motor_refresh_stops_on_disconnect(self):
        window = self.gui_module.GroundStation.__new__(self.gui_module.GroundStation)
        window.demo = False
        window.ros = types.SimpleNamespace(connected=lambda: False)
        window.last_arm_status = {"enabled": True, "motor_ready": True}
        window.motor_timer = Mock()
        window.motor_direction = 1
        window.send_command = Mock()
        window.refresh_motor()
        window.send_command.assert_called_once_with({"motor": "DC", "speed": 0})
        self.assertEqual(window.motor_direction, 0)

    def test_sensor_callback_updates_values_and_graph(self):
        window = self.gui_module.GroundStation.__new__(self.gui_module.GroundStation)
        window.started = 0
        window.sensor_source = Mock()
        for name in ("temperature", "pressure", "accel_x", "accel_y", "accel_z", "altitude"):
            setattr(window, name, Mock())
        for name in ("time_data", "temp_data", "pressure_data", "accel_x_data", "accel_y_data", "accel_z_data"):
            setattr(window, name, deque(maxlen=60))
        for name in ("temp_curve", "pressure_curve", "accel_x_curve", "accel_y_curve", "accel_z_curve"):
            setattr(window, name, Mock())
        window.receive_sensor_data({"mode": "hardware", "data": {"temperature": 24.5, "pressure": 101.2}})
        window.temperature.setText.assert_called_once_with("24.5 °C")
        window.accel_x.setText.assert_called_once_with("-- m/s²")
        window.sensor_source.setText.assert_called_once_with("LIVE SENSOR DATA")
        self.assertEqual(list(window.temp_data), [24.5])
        window.temp_curve.setData.assert_called_once()


if __name__ == "__main__":
    unittest.main()
