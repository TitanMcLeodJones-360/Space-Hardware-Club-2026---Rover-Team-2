# Rover electrical integration - 15 October 2026

This package updates the existing laptop -> ROS 2 -> Orange Pi -> USB -> Pico path using the main schematic in `two-month-electrical-schematic_5.7z` from the supplied Electrical Stuff archive. It includes the ground station, ROS bridge, custom messages, Arduino firmware, and tests. No repository changes have been pushed.

**First upload:** the Pico reads real sensors and writes SD logs, but `DRY_RUN = true` prevents actuator outputs. `USE_SERVOS = false` also keeps uncalibrated servos disabled. Firmware compilation and software tests do not prove physical hardware integration. This is based on the previously prepared code available in this workspace; compare with any later edits in your local working repository before merging.

## Wiring used by the code

| Function / schematic label | Pico GPIO | Physical header pin | Implementation |
| --- | --- | --- | --- |
| BNO055 + BMP388 SDA / I2C1_SDA | GP26 | 31 | Wire1 SDA |
| BNO055 + BMP388 SCL / I2C1_SCL | GP27 | 32 | Wire1 SCL |
| SD SO / SPI0_RX | GP16 | 21 | SPI MISO |
| SD CS / SPI0_CS | GP17 | 22 | Software chip select |
| SD CLK / SPI0_SCK | GP18 | 24 | SPI clock |
| SD SI / SPI0_TX | GP19 | 25 | SPI MOSI |
| DC / AXIS_0_PWM | GP2 | 4 | TB6612 PWMA |
| DC / AXIS_0_AIN2 | GP3 | 5 | TB6612 AIN2 |
| DC / AXIS_0_AIN1 | GP4 | 6 | TB6612 AIN1 |
| M1 / AXIS_1_PWM | GP15 | 20 | GUI Axis1 |
| M2 / AXIS_2_PWM | GP14 | 19 | GUI Axis2 |
| M3 / AXIS_3-1_PWM | GP13 | 17 | GUI Axis3A |
| M4 / AXIS_3-2_PWM | GP12 | 16 | GUI Axis3B |
| Orange Pi link | USB | USB connector | Newline-delimited JSON |

The schematic shows four servo channels and a DC motor on axis 0. The former five joint names (Base, Shoulder, Elbow, Wrist, Gripper) were replaced with the electrical channel names throughout this package. **Install the updated ROS package on BOTH computers together with this firmware.** Old GUI commands with those former names will be rejected.

Axis3A/B are channel labels, not confirmation of independent mechanical joints. Their relationship must be checked before enabling servo motion.

STBY has no external connection in the supplied schematic. The specified Adafruit TB6612 breakout has an onboard 10 kOhm STBY pull-up. The firmware supports that configuration with `MOTOR_STBY_PIN = -1` and `MOTOR_STBY_EXTERNALLY_ENABLED = true`; it never writes GPIO -1. A different TB6612 module may require an actual STBY wire. A GPIO-driven STBY can also be configured later. In either case software stop is not a battery disconnect.

The schematic supplies the sensor/SD logic from 3.3 V and actuators from the 6 V rail. Keep Electrical's power plan and common ground. The Adafruit 4682 SD board is 3.3 V only. Pico USB supplies the Pico in this schematic; VSYS/VBUS have no separate external power wire shown. The power LED is connected to the 6 V rail, not controlled by firmware. The separate block diagram shows a pull-stop; the main circuit sheet does not show its full wiring, which Electrical still needs to verify.

## 1. Verify and upload the Pico sketch

For a **standard RP2040 Raspberry Pi Pico only**, an optional prebuilt `firmware/Pico_RP2040_Bench.uf2` is included. Hold BOOTSEL while plugging that Pico into USB, then copy the UF2 onto the RPI-RP2 drive. It contains the default sensor/SD configuration with actuator outputs disabled. Use source/Arduino IDE for other board variants or any setting changes. See VALIDATION.md for exact build versions and checks.


Open `pico_arduino/rover_pico/rover_pico.ino` in Arduino IDE. Keep all five sketch files together. Use the Raspberry Pi Pico/RP2040/RP2350 board package by Earle F. Philhower, and select your actual board. For a standard RP2040 Pico, choose Tools -> CPU Speed -> 125 MHz. Validation for this package targets that board and clock setting.

Boards Manager URL:

```text
https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
```

Install ArduinoJson 7.x, Adafruit BNO055, Adafruit BMP3XX Library, and their BusIO/Unified Sensor dependencies. Wire, SPI, SD, and Servo come from the selected Pico core. Click Verify, then upload via BOOTSEL/UF2 for the first flash. The firmware copy under `rover_ros2/pico/rover_pico` is identical for packaging; edit/upload the `pico_arduino` copy.

Defaults in `config.h`:

```cpp
#define ROVER_DRY_RUN 1
#define ROVER_USE_SERVOS 0
constexpr bool USE_SENSORS = true;
constexpr bool USE_SD = true;
constexpr bool USE_DC_MOTOR = true;
```

These enable real sensing/logging but no actuator output. Addresses are BNO055 0x28 and BMP388 0x77, matching their default board configurations; check actual jumper settings if initialization fails. Use a tested FAT32 card. The firmware does not format cards. A 64 GB card may initially use exFAT.

## 2. Update BOTH ROS installations

Stop the old bridge and GUI first. Merge the supplied `rover_ros2` and `rover_interfaces` directories into the existing team's repository, preserving unrelated team files. Copy the same updated files to the Orange Pi. These instructions assume the repository is still `~/rover_ws/src/rover_team`; change that path if your laptop repository is elsewhere.

On each ROS computer, after copying the source:

```bash
source /opt/ros/jazzy/setup.bash
cd ~/rover_ws
colcon build --symlink-install \
  --base-paths src/rover_team/rover_interfaces src/rover_team/rover_ros2 \
  --packages-up-to rover_control
source ~/rover_ws/install/setup.bash
export ROS_DOMAIN_ID=2
export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET
```

The existing domain 2/WSL mirrored-network/firewall setup can be reused. Orange Pi dependencies: python3-serial, python3-colcon-common-extensions, and the existing Jazzy rclpy, std_msgs, launch_ros, and rosidl generators. Laptop GUI dependencies additionally include python3-pyqt5 and python3-pyqtgraph.

On Orange Pi, connect the Pico to a USB host port and find it:

```bash
ls -l /dev/serial/by-id/
ls -l /dev/ttyACM*
ros2 launch rover_control rover.launch.py dry_run:=false serial_port:=/dev/ttyACM0
```

Replace `/dev/ttyACM0` with the actual device; a stable `/dev/serial/by-id/...` name is preferable. Close Serial Monitor first. If permission is denied, add rover2 to dialout and reconnect the SSH session. The bridge's `dry_run:=false` means **use the real serial connection**. The Pico's default `ROVER_DRY_RUN 1` independently prevents physical actuator signals.

On laptop Ubuntu, launch the updated ground station:

```bash
ros2 launch rover_control ground_station.launch.py
```

It should show four servo channel controls, the DC motor controls, and sensor readings. The connection can say PICO SIMULATION while the sensor readings are real: the Pico mode refers to actuator outputs. `/arm/sensors` identifies real sensor packets with `simulated: false`; that flag alone does not prove all readings are valid.

## 3. Bench checks

1. Check status: `ros2 topic echo /arm/status rover_interfaces/msg/ArmStatus --once`. Look for `bridge_mode: serial`, `pico_online: true`, `imu_ready: true`, `bmp_ready: true`, `sd_ready: true`, a CSV filename, and an increasing `sd_rows` count.
2. Check actual telemetry: `ros2 topic echo /arm/sensors rover_interfaces/msg/SensorReadings --once`. Confirm finite temperature, pressure, all three acceleration components, and altitude. Tilt the IMU and compare the changing accelerometer readings. Its vector includes gravity.
3. In output dry run, Enable arm and send a target to Axis1. The returned target should change. Test STOP ALL and loss of the laptop heartbeat. This tests the command path; it does not demonstrate physical movement.
4. Leave sensing/logging running for a short disconnected-network test. Stop/power down before removing the SD card, and inspect the actual file. Logging does not require ROS or an enabled arm.
5. After real motor/servo activation, repeat physical stop/loss tests with Electrical and Mechanical. Verify the separate pull-stop cuts the required power; software cannot establish that.

Optional serial-only inspection, with the ROS bridge stopped:

```bash
python3 tools/pico_link_check.py /dev/ttyACM0 --seconds 10
```

This tool requests status, prints actual received frames, checks data/SD progress, and never sends an enable or motion command.

## Telemetry and logging

Both sensors share **Wire1 / I2C1**, not Wire / I2C0. Samples are targeted every 200 ms (5 Hz). The Pico sends JSON lines at 115200 baud; the Orange Pi publishes `/arm/sensors` and `/arm/status` using the existing custom message types. SD logging targets one CSV row every 1000 ms (1 Hz), saves missing data as blank cells, and reports errors through status. These are configured rates, not measured timing guarantees.

Each boot creates the next unused `LOG0000.CSV`, `LOG0001.CSV`, etc. Columns:

```csv
elapsed_ms,temperature_c,pressure_kpa,accel_x_m_s2,accel_y_m_s2,accel_z_m_s2,altitude_m
```

Temperature is from the BMP388 in degrees C, pressure is kPa, acceleration is m/s^2, and pressure-derived altitude is meters. Set the reference sea-level pressure for the test location. Elapsed time starts after peripheral initialization. Telemetry represents unavailable readings as JSON null / ROS NaN. Existing SD files are retained. Rows are flushed each second; the sensor's last available sample is used. Do not treat a nonzero row count as proof that all columns contain valid data.

## Physical output activation still needs these measurements

- Confirm which mechanism M1/M2/M3/M4 controls and whether Axis3A/B drive one coupled joint. If coupled, define and implement their synchronized motion before enabling them; independent GUI controls are only channel labels.
- Obtain each active servo's safe angle minimum/maximum, home angle, pulse endpoints in microseconds, and direction. Fill the `-1` values in JOINTS. `reversed` flips the pulse mapping. Do not substitute guessed 0-180 degree or 500-2500 microsecond limits.
- Once layout/coupling and calibration are correct, set `SERVO_LAYOUT_CONFIRMED = true` and `ROVER_USE_SERVOS 1`. Invalid settings prevent all actuator enablement in hardware mode.
- For a motor-only bench run, leave `ROVER_USE_SERVOS 0` and change `ROVER_DRY_RUN 0`. The actual DC motor path is wired and supports signed duty, a 30% initial limit, and release-to-stop. Verify physical direction; `MOTOR_DIRECTION = -1` reverses it. Without an encoder/limit switches, it cannot command measured speed or base angle or detect mechanical end stops.
- Outputs start disabled and require a fresh heartbeat plus Enable arm. A 1 second heartbeat lapse disables the arm, and a 300 ms motor-command lapse zeros motor duty. Reconnection does not re-enable it. STOP ALL detaches servo signals and zeros motor PWM; it neither holds a gravity-loaded arm nor cuts power. Peripheral/serial blocking can delay software timeouts, so verify timing on actual hardware.

## References

- Arduino-Pico Wire/Wire1: https://arduino-pico.readthedocs.io/en/latest/wire.html
- Arduino-Pico SPI: https://arduino-pico.readthedocs.io/en/latest/spi.html
- Adafruit TB6612 pinouts and STBY pull-up: https://learn.adafruit.com/adafruit-tb6612-h-bridge-dc-stepper-motor-driver-breakout/pinouts
- Adafruit 4682: https://www.adafruit.com/product/4682
- Supplied rover mission guide: data transmission + SD storage objectives and physical pull-stop requirements. The 5 Hz/1 Hz settings are this team's implementation choices.
