# Rover control 0.6.1

The laptop GUI controls four servo targets and a TB6612 motor through the Orange
Pi ROS 2 / USB bridge. The Pico continuously reads BNO055 acceleration and BMP388
temperature/pressure/altitude and logs to SD, including while outputs are stopped.

From this repository run `bash tools/build_workspace.sh` on each ROS computer.
On the Orange Pi launch `ros2 launch rover_control rover.launch.py`; on the laptop
launch `ros2 launch rover_control ground_station.launch.py`. Source ROS Jazzy,
the workspace, and set ROS_DOMAIN_ID=2 on both machines first. Hardware serial is
the rover launch default; use `dry_run:=true` only for software simulation.

The GUI provides Enable arm, 1-degree plus/minus buttons, numeric targets,
hold-to-run motor buttons, sensor plots, SD status, and STOP ALL OUTPUTS.
All four target zeros are 0 degrees, and initial software bounds are +/-10 degrees.

See [the installation guide](../README.md) for exact commands, wiring and the
zero/PWM assumptions. See [validation](../VALIDATION.md) for software checks and
remaining physical hardware validation.
