import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, Empty, Float32
from rover_interfaces.msg import JointCommand, ArmStatus, SensorReadings

from .protocol import validate_command
from .ros_messages import status_data, sensor_data


def live_qos():
    return QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                      durability=DurabilityPolicy.VOLATILE)


class GroundStationROS(Node):
    def __init__(self, on_status, on_sensors=None):
        super().__init__("ground_station")
        self.on_status = on_status
        self.on_sensors = on_sensors
        self.last_status = None
        self.last_sensors = None
        self.joint_publisher = self.create_publisher(JointCommand, "/arm/joint_command", live_qos())
        self.motor_publisher = self.create_publisher(Float32, "/arm/motor_command", live_qos())
        self.enable_publisher = self.create_publisher(Bool, "/arm/enable", live_qos())
        self.stop_publisher = self.create_publisher(Empty, "/arm/stop", live_qos())
        self.heartbeat = self.create_publisher(Bool, "/arm/heartbeat", live_qos())
        self.status_sub = self.create_subscription(ArmStatus, "/arm/status", self.receive_status, live_qos())
        self.sensor_sub = self.create_subscription(SensorReadings, "/arm/sensors", self.receive_sensors, live_qos())
        self.heartbeat_timer = self.create_timer(0.2, self.send_heartbeat)

    def send_command(self, request):
        request = validate_command(request)
        command = request.get("command")
        if command is not None and command not in ("ARM_ENABLE", "STOP_ALL"):
            raise ValueError("This control command is internal")
        safe_stop = command == "STOP_ALL" or request.get("speed") == 0
        if not safe_stop and not self.connected():
            raise ValueError("No recent arm status; command not sent")
        if command == "STOP_ALL":
            self.stop_publisher.publish(Empty())
        elif command == "ARM_ENABLE":
            msg = Bool()
            msg.data = True
            self.enable_publisher.publish(msg)
        elif "axis" in request:
            msg = JointCommand()
            msg.joint = request["axis"]
            msg.angle_deg = float(request["angle"])
            self.joint_publisher.publish(msg)
        else:
            msg = Float32()
            msg.data = float(request["speed"])
            self.motor_publisher.publish(msg)

    def send_heartbeat(self):
        msg = Bool()
        msg.data = True
        self.heartbeat.publish(msg)

    def receive_status(self, msg):
        try:
            status = status_data(msg)
        except (ValueError, TypeError):
            return
        self.last_status = time.monotonic()
        self.on_status(status)

    def receive_sensors(self, msg):
        try:
            packet = sensor_data(msg)
        except (ValueError, TypeError):
            return
        self.last_sensors = time.monotonic()
        if self.on_sensors:
            self.on_sensors(packet)

    def connected(self):
        return self.last_status is not None and time.monotonic() - self.last_status < 1.5

    def poll(self):
        # The Qt timer gives this node time to process ROS callbacks.
        rclpy.spin_once(self, timeout_sec=0.0)

    def close(self):
        self.send_command("STOP_ALL")
        rclpy.spin_once(self, timeout_sec=0.0)
        self.destroy_node()
