# How the integrated rover software works

The laptop's `ground_station.py` builds the Qt GUI. Its `ground_station_ros.py`
node publishes target angles, enable/stop commands, DC motor duty requests, and
an operator heartbeat. It displays real sensor readings and requested targets;
there are no per-joint position sensors in the schematic.

On the Orange Pi, `arm_bridge.py` translates ROS 2 messages to newline-delimited
JSON over USB serial. It publishes the Pico's status and sensor packets back to
ROS. It checks operator and Pico freshness and marks disconnected data stale.
It does not drive GPIO itself. `rover_arm.py` is used only for software simulation.

On the Pico, `rover_pico.ino` handles JSON, attaches servo outputs only after
explicit enable, applies pulse ramps, controls the TB6612, and schedules sensor
reads, status replies and SD writes. `control.h` implements bounds, enable/stop
rules, heartbeats, motor timeout and the ramp state without Arduino dependencies.
`config.h` holds pins, startup targets, provisional angle/pulse mappings, and rates.
The four target homes are zero; initial limits are +/-10 degrees. Electrical center
is assumed to be 1500 us and is not a measurement of the installed arm.

`sensors.h` reads BNO055 acceleration and BMP388 temperature/pressure through I2C0.
It calculates altitude from pressure and a configurable sea-level reference.
`sd_logger.h` creates a new CSV each boot and flushes one row per second. Missing
sensor fields are null over serial and blank in CSV. The Pico keeps collecting
and logging when servo and motor outputs are stopped.

A valid operator heartbeat plus Enable arm is required for motion. Heartbeat
loss, USB disconnect, invalid commands, or Stop disable outputs. Reconnection
requires another explicit enable. Stop freezes pending ramps, detaches servo
pulses and zeros motor PWM; a gravity-loaded arm still needs physical support.
A watchdog recovers from peripheral hangs, with outputs stopped after reset.

Build and installation commands are in [README](../README.md).
