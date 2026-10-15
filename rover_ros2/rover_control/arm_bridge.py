import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Empty, Float32
from rover_interfaces.msg import JointCommand, ArmStatus, SensorReadings

from .ground_station_ros import live_qos
from .rover_arm import RoverArm
from .protocol import validate_command, valid_sensor_packet
from .ros_messages import status_message, sensor_message


class ArmBridge(Node):
    def __init__(self):
        super().__init__("arm_bridge")
        self.declare_parameter("dry_run", True)
        self.declare_parameter("serial_port", "")
        self.declare_parameter("baudrate", 115200)
        self.dry_run = self.get_parameter("dry_run").value
        self.last_heartbeat = None
        self.last_pico_status = None
        self.serial = None
        self.buffer = b""
        self.arm = None
        self.status_data = {"ready": False, "enabled": False, "note": "Waiting for Pico"}
        self.publisher = self.create_publisher(ArmStatus, "/arm/status", live_qos())
        self.sensor_publisher = self.create_publisher(SensorReadings, "/arm/sensors", live_qos())
        self.joint_sub = self.create_subscription(
            JointCommand, "/arm/joint_command", self.receive_joint, live_qos())
        self.motor_sub = self.create_subscription(
            Float32, "/arm/motor_command", self.receive_motor, live_qos())
        self.enable_sub = self.create_subscription(
            Bool, "/arm/enable", self.receive_enable, live_qos())
        self.stop_sub = self.create_subscription(
            Empty, "/arm/stop", self.receive_stop, live_qos())
        self.heartbeat_sub = self.create_subscription(
            Bool, "/arm/heartbeat", self.receive_heartbeat, live_qos())

        if self.dry_run:
            self.arm = RoverArm(dry_run=True)
            self.status_data = self.arm.setup_servos()
            self.get_logger().info("SIMULATION: no serial port or servo outputs")
        else:
            import serial
            port = self.get_parameter("serial_port").value
            if not port:
                raise ValueError("Set serial_port for Pico USB serial, UART, or a USB-UART adapter")
            self.serial = serial.Serial(port, self.get_parameter("baudrate").value,
                                        timeout=0, write_timeout=0.1)
            self.serial.reset_input_buffer()
            self.write_command("LINK_LOST")

        self.poll_timer = self.create_timer(0.02, self.poll)
        self.status_timer = self.create_timer(0.25, self.query_status)

    def operator_online(self):
        return self.last_heartbeat is not None and time.monotonic() - self.last_heartbeat < 0.8

    def pico_online(self):
        return self.last_pico_status is not None and time.monotonic() - self.last_pico_status < 1.0

    def receive_heartbeat(self, msg):
        if msg.data:
            if self.last_heartbeat is not None and not self.operator_online():
                self.write_command("LINK_LOST")
            self.last_heartbeat = time.monotonic()
            self.write_command("HEARTBEAT")

    def receive_joint(self, msg):
        self.forward_command({"axis": msg.joint, "angle": msg.angle_deg})

    def receive_motor(self, msg):
        self.forward_command({"motor": "DC", "speed": msg.data})

    def receive_enable(self, msg):
        self.forward_command("ARM_ENABLE" if msg.data else "STOP_ALL")

    def receive_stop(self, msg):
        self.forward_command("STOP_ALL")

    def forward_command(self, request):
        try:
            request = validate_command(request)
        except (ValueError, TypeError) as exc:
            self.publish_error(str(exc))
            return
        command = request.get("command")
        if command is not None and command not in ("ARM_ENABLE", "STOP_ALL"):
            self.publish_error("Internal command cannot be sent by the GUI")
            return
        safe_stop = command == "STOP_ALL" or (request.get("motor") == "DC" and request["speed"] == 0)
        if not safe_stop and not self.operator_online():
            self.publish_error("Ground station heartbeat missing")
            return
        if not safe_stop and not self.dry_run and not self.pico_online():
            self.publish_error("No recent Pico reply")
            return
        self.write_command(request)

    def write_command(self, command):
        command = validate_command(command)
        if self.arm is not None:
            self.status_data = self.arm.handle_command(command)
        elif self.serial is not None:
            try:
                frame = (json.dumps(command) + "\n").encode("ascii")
                if self.serial.write(frame) != len(frame):
                    raise OSError("Incomplete serial write")
            except Exception as exc:
                self.get_logger().error("Serial write failed: " + str(exc))
                self.serial.close()
                self.serial = None
                self.last_pico_status = None
                self.status_data = {"ready": False, "enabled": False,
                                    "error": "Serial lost; restart the bridge"}

    def poll(self):
        if not self.operator_online():
            if self.arm is not None and self.arm.enabled:
                self.write_command("LINK_LOST")
            elif self.serial is not None and self.status_data.get("enabled"):
                self.write_command("LINK_LOST")
        if (self.arm is not None and self.arm.motor_speed != 0 and
                time.monotonic() - self.arm.motor_updated >= 0.3):
            self.arm.motor_speed = 0
            self.status_data = self.arm.status()
        if self.serial is None:
            return
        try:
            self.buffer += self.serial.read(min(self.serial.in_waiting, 4096))
            if len(self.buffer) > 8192:
                self.buffer = b""
                self.publish_error("Oversized serial reply")
                return
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    status = json.loads(line.decode("utf-8"))
                    if valid_sensor_packet(status):
                        self.sensor_publisher.publish(sensor_message(status))
                        continue
                    if (isinstance(status, dict) and
                            isinstance(status.get("enabled"), bool) and
                            isinstance(status.get("ready"), bool) and
                            status.get("mode") in ("hardware", "simulation")):
                        status_message(status)  # Check before accepting this reply.
                        self.status_data = status
                        self.last_pico_status = time.monotonic()
                except (ValueError, TypeError, UnicodeError, OverflowError, AssertionError):
                    self.get_logger().warning("Ignoring invalid Pico reply")
        except Exception as exc:
            self.serial.close()
            self.serial = None
            self.last_pico_status = None
            self.publish_error("Serial read failed: " + str(exc))

    def query_status(self):
        self.write_command("STATUS")
        self.publish_status()

    def publish_error(self, message):
        self.publish_status(error=message)

    def publish_status(self, error=None):
        status = dict(self.status_data)
        status["bridge_mode"] = "simulation" if self.dry_run else "serial"
        status["operator_online"] = self.operator_online()
        status["pico_online"] = self.pico_online() if not self.dry_run else False
        if not self.dry_run and not self.pico_online():
            status["ready"] = False
            status["enabled"] = False
            status["note"] = "Pico disconnected or not replying"
        if error:
            status["error"] = error
        self.publisher.publish(status_message(status))

    def close(self):
        self.write_command("STOP_ALL")
        if self.serial is not None:
            self.serial.close()
        self.destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ArmBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()
