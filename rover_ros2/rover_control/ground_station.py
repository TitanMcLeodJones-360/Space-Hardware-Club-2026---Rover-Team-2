import sys
import random
import time
from datetime import datetime
from collections import deque

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QTextEdit,
    QGroupBox,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QDoubleSpinBox,
)

import pyqtgraph as pg

class GroundStation(QMainWindow):

    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.ros = None
        self.arm_buttons = []
        self.axis_widgets = {}
        self.motor_widgets = []
        self.motor_direction = 0
        self.last_arm_status = None
        self.angle_inputs = {}
        self.target_synced = set()
        self.started = time.monotonic()
        self.setWindowTitle("Rover Control Station")
        self.resize(1300, 800)
        # Store last 60 sensor readings
        self.max_points = 60
        self.time_data = deque(maxlen=self.max_points)
        self.temp_data = deque(maxlen=self.max_points)
        self.pressure_data = deque(maxlen=self.max_points)
        self.accel_x_data = deque(maxlen=self.max_points)
        self.accel_y_data = deque(maxlen=self.max_points)
        self.accel_z_data = deque(maxlen=self.max_points)
        self.counter = 0
        self.build_ui()
        self.log("Ground station initialized")
        if self.demo:
            self.preview_status = {
                "ready": True, "enabled": False, "mode": "simulation",
                "targets": {axis: 90 for axis in ("Base", "Shoulder", "Elbow", "Wrist", "Gripper")},
                "limits": {axis: [0, 180] for axis in ("Base", "Shoulder", "Elbow", "Wrist", "Gripper")},
                "motor_ready": True, "motor_speed": 0, "motor_limit": 30,
                "note": "Local UI preview only",
            }
            self.start_demo_telemetry()
            self.log("LOCAL DEMO: fake sensors, no ROS 2 or hardware")
            self.receive_arm_status(self.preview_status)
        else:
            from .ground_station_ros import GroundStationROS
            self.ros = GroundStationROS(self.receive_arm_status, self.receive_sensor_data)
            self.connection.setText("WAITING FOR ARM BRIDGE")
            self.log("ROS 2 started; waiting for arm status. Sensors are not connected.")
            self.ros_timer = QTimer(self)
            self.ros_timer.timeout.connect(self.poll_ros)
            self.ros_timer.start(20)

    def build_ui(self):

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        header = QHBoxLayout()
        title = QLabel("Rover Control Station")
        title.setObjectName("title")
        self.connection = QLabel("DEMO MODE")
        self.connection.setObjectName("connection")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("ROS 2:"))
        header.addWidget(self.connection)
        main_layout.addLayout(header)
        content = QHBoxLayout()
        # Left side
        left_column = QVBoxLayout()

        left_column.addWidget(self.create_servo_panel())
        left_column.addWidget(self.create_motor_panel())
        # Right side
        right_column = QVBoxLayout()
        right_column.addWidget(self.create_sensor_panel())
        right_column.addWidget(self.create_graph_panel())
        content.addLayout(left_column, 1)
        content.addLayout(right_column, 2)
        main_layout.addLayout(content)
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        log_layout.addWidget(self.log_box)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        stop_button = QPushButton('STOP ALL OUTPUTS')
        stop_button.setObjectName('emergency')
        stop_button.clicked.connect(self.stop_all)
        main_layout.addWidget(stop_button)
        self.apply_style()

    def create_servo_panel(self):
        group = QGroupBox("Arm target angles")
        layout = QGridLayout()
        for row, axis in enumerate(("Base", "Shoulder", "Elbow", "Wrist", "Gripper")):
            angle = QDoubleSpinBox()
            angle.setRange(0, 180)  # Preview range; real limits come from the Pico.
            angle.setDecimals(1)
            angle.setSuffix("°")
            self.angle_inputs[axis] = angle
            minus = QPushButton("-")
            plus = QPushButton("+")
            send = QPushButton("Set")
            minus.clicked.connect(lambda checked, axis=axis: self.change_target(axis, -5))
            plus.clicked.connect(lambda checked, axis=axis: self.change_target(axis, 5))
            send.clicked.connect(lambda checked, axis=axis: self.send_angle(axis))
            self.axis_widgets[axis] = [angle, minus, plus, send]
            self.arm_buttons.extend(self.axis_widgets[axis])
            for column, widget in enumerate((QLabel(axis), minus, angle, plus, send)):
                layout.addWidget(widget, row, column)
        for widget in self.arm_buttons:
            widget.setEnabled(False)
        self.enable_button = QPushButton("Enable arm")
        self.enable_button.setEnabled(False)
        self.enable_button.clicked.connect(lambda: self.send_command("ARM_ENABLE"))
        layout.addWidget(self.enable_button, 5, 0, 1, 5)
        self.arm_targets = QLabel("Targets: -- (no position feedback)")
        self.arm_targets.setWordWrap(True)
        layout.addWidget(self.arm_targets, 6, 0, 1, 5)
        group.setLayout(layout)
        return group

    def create_motor_panel(self):
        group = QGroupBox("DC motor (TB6612)")
        layout = QGridLayout()
        self.motor_input = QDoubleSpinBox()
        self.motor_input.setRange(0, 30)
        self.motor_input.setValue(15)
        self.motor_input.setSuffix("%")
        self.motor_speed_label = QLabel("Requested speed: 0%")
        forward = QPushButton("Hold forward")
        reverse = QPushButton("Hold reverse")
        stop = QPushButton("Stop motor")
        forward.pressed.connect(lambda: self.start_motor(1))
        reverse.pressed.connect(lambda: self.start_motor(-1))
        forward.released.connect(self.stop_motor)
        reverse.released.connect(self.stop_motor)
        stop.clicked.connect(self.stop_motor)
        self.motor_widgets = [self.motor_input, forward, reverse]
        for widget in self.motor_widgets:
            widget.setEnabled(False)
        layout.addWidget(self.motor_input, 0, 0)
        layout.addWidget(forward, 0, 1)
        layout.addWidget(reverse, 0, 2)
        layout.addWidget(stop, 0, 3)
        layout.addWidget(self.motor_speed_label, 1, 0, 1, 4)
        group.setLayout(layout)
        self.motor_timer = QTimer(self)
        self.motor_timer.timeout.connect(self.refresh_motor)
        return group

    def start_motor(self, direction):
        self.motor_direction = direction
        self.refresh_motor()
        if self.motor_direction:
            self.motor_timer.start(100)

    def refresh_motor(self):
        status = self.last_arm_status or {}
        online = self.demo or self.ros.connected()
        if not online or not status.get("enabled") or not status.get("motor_ready"):
            self.stop_motor()
            return
        self.send_command({"motor": "DC", "speed": self.motor_direction * self.motor_input.value()})

    def stop_motor(self):
        self.motor_timer.stop()
        self.motor_direction = 0
        self.send_command({"motor": "DC", "speed": 0})

    def create_sensor_panel(self):

        group = QGroupBox('Live Sensor Readings')
        layout = QGridLayout()
        self.temperature = QLabel("-- °C")
        self.pressure = QLabel("-- kPa")
        self.accel_x = QLabel("-- m/s²")
        self.accel_y = QLabel("-- m/s²")
        self.accel_z = QLabel("-- m/s²")
        self.altitude = QLabel("-- m")
        sensors = [
            (
                "Temperature",
                self.temperature
            ),
            (
                "Pressure",
                self.pressure
            ),
            (
                "Acceleration X",
                self.accel_x
            ),
            (
                "Acceleration Y",
                self.accel_y
            ),
            (
                "Acceleration Z",
                self.accel_z
            ),
            (
                "Altitude",
                self.altitude
            )
        ]
        for row, (name, value) in enumerate(sensors):
            layout.addWidget(QLabel(name), row, 0)
            value.setObjectName('sensorValue')
            layout.addWidget(value, row, 1)
        self.sensor_source = QLabel("Waiting for sensor data")
        layout.addWidget(self.sensor_source, len(sensors), 0, 1, 2)
        self.sd_status = QLabel("SD logging: waiting for Pico")
        layout.addWidget(self.sd_status, len(sensors) + 1, 0, 1, 2)
        group.setLayout(layout)
        return group

    def create_graph_panel(self):

        group = QGroupBox('Live Telemetry')
        layout = QVBoxLayout()
        self.temp_plot = pg.PlotWidget()
        self.temp_plot.setTitle('Temperature')
        self.temp_plot.setLabel('left', 'Temperature', units='°C')
        self.temp_plot.setLabel('bottom', 'Time', units='s')
        self.temp_plot.showGrid(x=True, y=True, alpha=0.2)
        self.temp_curve = self.temp_plot.plot(pen=pg.mkPen(width=2))
        layout.addWidget(self.temp_plot)
        self.pressure_plot = pg.PlotWidget()
        self.pressure_plot.setTitle('Pressure')
        self.pressure_plot.setLabel('left', 'Pressure', units='kPa')
        self.pressure_plot.setLabel('bottom', 'Time', units='s')
        self.pressure_plot.showGrid(x=True, y=True, alpha=0.2)
        self.pressure_curve = self.pressure_plot.plot(pen=pg.mkPen(width=2))
        layout.addWidget(self.pressure_plot)
        self.accel_plot = pg.PlotWidget()
        self.accel_plot.setTitle('Acceleration')
        self.accel_plot.setLabel('left', 'Acceleration', units='m/s²')
        self.accel_plot.setLabel('bottom', 'Time', units='s')
        self.accel_plot.showGrid(x=True, y=True, alpha=0.2)
        self.accel_x_curve = self.accel_plot.plot(name='X')
        self.accel_y_curve = self.accel_plot.plot(name='Y')
        self.accel_z_curve = self.accel_plot.plot(name='Z')
        layout.addWidget(self.accel_plot)
        group.setLayout(layout)
        return group

    def send_command(self, request):
        if __package__:
            from .protocol import validate_command
        else:
            from protocol import validate_command
        try:
            request = validate_command(request)
            if self.demo:
                command = request.get("command")
                if command == "ARM_ENABLE":
                    self.preview_status["enabled"] = True
                elif command == "STOP_ALL":
                    self.preview_status["enabled"] = False
                    self.preview_status["motor_speed"] = 0
                elif "axis" in request and self.preview_status["enabled"]:
                    self.preview_status["targets"][request["axis"]] = request["angle"]
                elif "motor" in request and self.preview_status["enabled"]:
                    self.preview_status["motor_speed"] = request["speed"]
                self.log(f"UI preview: {request}")
                self.receive_arm_status(self.preview_status)
            else:
                self.ros.send_command(request)
                self.log(f"Published: {request}")
        except (ValueError, RuntimeError) as exc:
            self.log(str(exc))

    def send_angle(self, axis):
        self.send_command({"axis": axis, "angle": self.angle_inputs[axis].value()})

    def receive_sensor_data(self, packet):
        self.update_sensors(packet["data"], packet["mode"])

    def receive_arm_status(self, status):
        self.last_arm_status = status
        ready = bool(status.get("ready"))
        enabled = bool(status.get("enabled"))
        mode = status.get("mode", "unknown")
        if self.demo:
            label = "LOCAL DEMO"
        elif status.get("bridge_mode") == "simulation":
            label = "ROS 2 / SIMULATION"
        elif status.get("pico_online"):
            label = "ROS 2 / PICO " + mode.upper()
        else:
            label = "ROS 2 / NO PICO REPLY"
        self.connection.setText(label + (" / ENABLED" if enabled else " / STOPPED"))
        for button in self.arm_buttons:
            button.setEnabled(ready and enabled)
        self.enable_button.setEnabled(ready and not enabled)
        for axis, widgets in self.axis_widgets.items():
            for widget in widgets:
                widget.setEnabled(ready and enabled and axis in status.get("limits", {}))
        motor_ready = bool(status.get("motor_ready"))
        for widget in self.motor_widgets:
            widget.setEnabled(ready and enabled and motor_ready)
        if "motor_limit" in status:
            self.motor_input.setRange(0, abs(status["motor_limit"]))
        self.motor_speed_label.setText(f"Requested speed: {status.get('motor_speed', 0):g}%")
        if not enabled and self.motor_direction:
            self.motor_timer.stop()
            self.motor_direction = 0
        if "sd_ready" in status:
            if status["sd_ready"]:
                self.sd_status.setText(f"SD logging: {status.get('sd_file', '')}, {status.get('sd_rows', 0)} rows")
            else:
                self.sd_status.setText("SD logging: " + status.get("sd_error", "not ready"))
        else:
            self.sd_status.setText("SD logging: unavailable in simulation")
        targets = status.get("targets", {})
        for axis, values in status.get("limits", {}).items():
            if axis in self.angle_inputs and all(isinstance(v, (int, float)) for v in values):
                self.angle_inputs[axis].setRange(*values)
        for axis, value in targets.items():
            if axis in self.angle_inputs and axis not in self.target_synced:
                self.angle_inputs[axis].setValue(value)
                self.target_synced.add(axis)
        self.arm_targets.setText("Targets: " + ", ".join(
            f"{name} {angle:g}°" for name, angle in targets.items()) +
            " (requested values, not position feedback)")
        note = status.get("error") or status.get("sensor_error") or status.get("note", "")
        if note and note != getattr(self, "last_note", None):
            self.log(note)
            self.last_note = note

    def poll_ros(self):
        self.ros.poll()
        if not self.ros.connected():
            self.connection.setText("NO RECENT ARM STATUS")
            self.target_synced.clear()
            self.enable_button.setEnabled(False)
            self.motor_timer.stop()
            self.motor_direction = 0
            for widget in self.motor_widgets:
                widget.setEnabled(False)
            self.motor_speed_label.setText("Requested speed: -- (connection lost)")
            self.sd_status.setText("SD logging: status stale")
            for button in self.arm_buttons:
                button.setEnabled(False)
        if self.ros.last_sensors is None or time.monotonic() - self.ros.last_sensors > 2:
            self.sensor_source.setText("No recent sensor data")

    def closeEvent(self, event):
        self.motor_timer.stop()
        if self.ros is not None:
            self.ros_timer.stop()
            self.ros.close()
        event.accept()

    def change_target(self, axis, amount):
        field = self.angle_inputs[axis]
        field.setValue(field.value() + amount)
        self.send_angle(axis)

    def stop_all(self):

        self.motor_timer.stop()
        self.motor_direction = 0
        self.send_command('STOP_ALL')
        self.log('Stop requested; waiting for arm status')

    def start_demo_telemetry(self):

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_demo_sensors)
        # Update every second
        self.timer.start(1000)

    def update_demo_sensors(self):
        self.update_sensors({
            "temperature": random.uniform(23, 26),
            "pressure": random.uniform(100.5, 101.8),
            "accel_x": random.uniform(-0.2, 0.2),
            "accel_y": random.uniform(-0.2, 0.2),
            "accel_z": random.uniform(9.7, 9.9),
            "altitude": random.uniform(180, 182),
        }, "simulation")

    def update_sensors(self, data, mode):
        self.sensor_source.setText("SIMULATED SENSOR DATA" if mode == "simulation" else "LIVE SENSOR DATA")
        readings = (
            ("temperature", self.temperature, "°C", 1),
            ("pressure", self.pressure, "kPa", 2),
            ("accel_x", self.accel_x, "m/s²", 2),
            ("accel_y", self.accel_y, "m/s²", 2),
            ("accel_z", self.accel_z, "m/s²", 2),
            ("altitude", self.altitude, "m", 1),
        )
        for key, label, unit, decimals in readings:
            value = data.get(key)
            label.setText(f"{value:.{decimals}f} {unit}" if value is not None else f"-- {unit}")
        self.time_data.append(time.monotonic() - self.started)
        for key, history, curve in (
            ("temperature", self.temp_data, self.temp_curve),
            ("pressure", self.pressure_data, self.pressure_curve),
            ("accel_x", self.accel_x_data, self.accel_x_curve),
            ("accel_y", self.accel_y_data, self.accel_y_curve),
            ("accel_z", self.accel_z_data, self.accel_z_curve),
        ):
            value = data.get(key)
            history.append(value if value is not None else float("nan"))
            curve.setData(list(self.time_data), list(history))

    def log(
        self,
        message
    ):

        current_time = datetime.now().strftime('%H:%M:%S')
        self.log_box.append(f'[{current_time}] {message}')

    def apply_style(self):

        self.setStyleSheet("""
        QMainWindow {
            background-color: #f5f7fa;
        }

        QLabel {
            color: #17202a;
            font-size: 14px;
        }

        QLabel#title {
            color: #17202a;
            font-size: 30px;
            font-weight: bold;
            padding: 10px;
        }

        QLabel#connection {
            color: #d68910;
            font-size: 16px;
            font-weight: bold;
        }

        QLabel#sensorValue {
            color: #117a43;
            font-size: 15px;
            font-weight: bold;
        }

        QGroupBox {
            background-color: white;
            color: #17202a;
            border: 1px solid #d5dce3;
            border-radius: 8px;
            margin-top: 20px;
            padding: 15px;
            font-size: 17px;
            font-weight: bold;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 5px;
        }

        QPushButton {
            background-color: #2874a6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 12px;
            font-size: 14px;
            min-height: 20px;
        }

        QPushButton:hover {
            background-color: #21618c;
        }

        QPushButton:pressed {
            background-color: #1b4f72;
        }

        QTextEdit {
            background-color: white;
            color: #17202a;
            border: 1px solid #ccd1d1;
            border-radius: 5px;
            font-family: Consolas;
            font-size: 13px;
        }

        QPushButton#emergency {
            background-color: #c0392b;
            color: white;
            font-size: 20px;
            font-weight: bold;
            min-height: 55px;
        }

        QPushButton#emergency:hover {
            background-color: #a93226;
        }
        """)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Rover arm ground station")
    parser.add_argument("--demo", action="store_true", help="Local preview, no ROS 2")
    args, _ = parser.parse_known_args()
    ros = None
    if not args.demo:
        try:
            import rclpy as ros
        except ImportError:
            raise SystemExit("Source your ROS 2 installation, or run with --demo for a local preview.")
        ros.init(args=None)
    app = QApplication(sys.argv)
    try:
        window = GroundStation(demo=args.demo)
        window.show()
        result = app.exec_()
    finally:
        if ros is not None and ros.ok():
            ros.shutdown()
    return result

if __name__ == "__main__":
    sys.exit(main())
