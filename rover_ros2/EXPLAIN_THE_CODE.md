# How this code works

## The three places code runs

The laptop runs the buttons and graphs. Its `ground_station` ROS node publishes commands and subscribes to replies.

The Orange Pi runs the `arm_bridge` ROS node. It receives commands through ROS, checks the connection, and sends them to the Pico over USB serial. It also sends the Pico's readings back through ROS.

The Pico runs Arduino C++. It makes the PWM signals, reads the sensors, and writes the SD log. It is not a ROS node in this setup.

## Example: move Axis1 to 95 degrees

1. You press Set beside Axis1 in the GUI.
2. `GroundStationROS.send_command()` fills a `JointCommand`: joint = Axis1, angle_deg = 95.0.
3. The ground station publishes that message on `/arm/joint_command`.
4. The Orange Pi's subscriber calls `ArmBridge.receive_joint()` when the message arrives.
5. The bridge checks the heartbeat and recent Pico reply, then sends an axis/angle JSON line over serial.
6. The Pico checks that outputs are enabled, limits the target to the configured range, and updates that servo's pulse.
7. The Pico reports its requested targets. The bridge publishes `ArmStatus`, which the GUI displays.

The target is not a measured joint position. We would need feedback hardware to know the real position.

## The ROS words

A node is a running ROS program. A publisher sends messages. A subscriber listens for them. A topic is the named channel they use. A callback is the function ROS calls when a message arrives.

In `arm_bridge.py`, `create_subscription()` connects `/arm/joint_command` to `receive_joint()`. That short callback is where an incoming joint message becomes a Pico command.

The `.msg` files describe the data fields. `JointCommand.msg` has a joint name and an angle in degrees. `ArmStatus.msg` has enable state, requested targets, limits, and SD status. `SensorReadings.msg` has the sensor values and their units. `colcon` builds these into classes the nodes can import.

## Sensor readings coming back

The Pico reads the BNO055 and BMP388 every 200 ms. It sends temperature, pressure, acceleration on three axes, and altitude to the Orange Pi. `ArmBridge.poll()` reads the serial lines and publishes `SensorReadings` on `/arm/sensors`. The ground station subscriber receives it and updates the labels and graphs.

The Pico also saves the latest readings once per second to a CSV file. This logging continues if the ground station disconnects. Missing values stay blank in the log and show as unavailable in the GUI.

## Why there is still JSON

ROS messages are used between the laptop and Orange Pi. JSON is only the simple serial format between the Orange Pi and Pico. `ros_messages.py` converts between those formats. `protocol.py` checks the serial command values; it is a local file, not a pip package.

## Stop and heartbeat

The GUI sends a small heartbeat every 200 ms. Losing that heartbeat stops outputs and requires Enable arm again after reconnecting. The Pico has its own heartbeat timeout too.

Motor buttons send a signed duty percentage while held. Releasing sends zero. If refreshed motor commands stop arriving, the Pico zeros the motor after 300 ms. This is basic speed control, not positioning or encoder feedback.

STOP ALL removes servo pulses and zeros the motor. It does not actively hold a loaded arm or replace the physical pull-stop.

## Where to start reading

Read `JointCommand.msg`, then `GroundStationROS.send_command()`, then `ArmBridge.receive_joint()` and `write_command()`. Those show the whole command path. After that, read `handleCommand()` and `applyServo()` in the Arduino sketch.

The GUI uses a Qt timer to let the ground station node process ROS callbacks. The Orange Pi node uses `rclpy.spin()`. Both are `Node` subclasses with publishers and subscribers.

## What is still unfinished

GPIOs now match the supplied schematic. Mechanical must confirm servo layout, coupling, pulse widths, home angles, and movement limits in `config.h`. The defaults are a dry run. The full ROS build and hardware tests still need to be done on the actual laptop, Orange Pi, and Pico.
