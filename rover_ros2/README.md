# ROS 2 rover control

This release uses the schematic's four servo channels: Axis1, Axis2, Axis3A, Axis3B. Axis 0 is the DC motor. The earlier Base/Shoulder/Elbow/Wrist/Gripper names are no longer accepted. Update laptop and Orange Pi together.

See the package's top-level README.md for building, dependencies, launching, topics, physical wiring, telemetry, SD logging, testing, and calibration. The node/launch names and custom message definitions are unchanged. Do not run the old bridge and the new one together.

The bridge relays JSON lines to Pico over USB serial and publishes custom rover_interfaces messages over ROS 2. Launch with dry_run:=false and serial_port:=... to reach the real Pico. The default launch dry_run:=true instead runs a computer-side simulation without USB.

Topics: /arm/joint_command (JointCommand), /arm/motor_command (std_msgs/Float32), /arm/enable (std_msgs/Bool), /arm/stop (std_msgs/Empty), /arm/heartbeat (std_msgs/Bool), /arm/status (ArmStatus), /arm/sensors (SensorReadings).

Run Python tests: `python3 -m unittest discover -s rover_ros2/tests -p 'test_*.py'` from the package root. They use ROS message/node doubles; a ROS installation and hardware are not required for those tests. This does not replace a real colcon build or network/serial/hardware test.

## Wired Xbox controller update

See `../XBOX_SETUP.md`. Launch `ground_station.launch.py xbox:=true xbox_source:=windows` for the Windows helper + mirrored WSL, or `xbox:=true xbox_source:=ros` for a controller directly recognized by native Ubuntu/SDL. The default remains mouse controls. Start enables with neutral sticks and RB held; RB must stay held for movement. B/Back, RB release, stale input, or GUI close stop outputs. One ground station owns both commands and the heartbeat.
