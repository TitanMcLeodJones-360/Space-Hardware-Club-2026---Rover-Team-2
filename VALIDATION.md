# Rover complete release 0.6.1 — validation

Prepared 24 October 2026 against team branch commit
`7822470541d73fa0188925f7d8401644465582bd`.

## Checks for this package

- 48 Python tests passed: command validation, GUI callbacks, heartbeat/status
  freshness, telemetry conversion, command gating, serial failures, every split
  boundary, UTF-8/CRLF, startup fragments, valid first replies, malformed and
  oversized lines and subsequent packet recovery.
- The suite includes real pySerial 3.5 with a POSIX pseudo-terminal for split
  frames and rejection of a second exclusive opener. ROS and Qt use the project's
  doubles; this does not exercise a ROS executor or a rendered GUI.
- Native C++ controls passed under `-Wall -Wextra -Werror` in hardware, dry-run and
  motor-only profiles: stopped startup, limits, ramps, stopped pending moves,
  heartbeat loss, no automatic re-enable, motor timeout and time rollover.
- Both copies of the five Pico sources match each other and the previously
  compiled integrated 0.6.0 package byte-for-byte.
- UF2 SHA-256:
  `ac834ef9e70b8027f4b6c7b907f67f61fbaf31e6a2b3c8e2bf14365ecfd35510`.
  Its 575 blocks, magic values, RP2040 family, numbering and payloads were checked.
- Python syntax, Bash scripts and README Bash blocks were checked. Setup/package
  versions match 0.6.1, launch entry points name existing modules, and runtime code
  has no Xbox imports, entry points or helper files.
- The Python updater was exercised in isolated Git checkouts: exact file/staging
  lists, backups, obsolete-file removal, repeat application, unrelated file and
  ignore-rule preservation, plus refusal of damaged payloads, wrong branches and
  unrelated staged changes. SHA-256 validation precedes writes.

## Retained firmware build provenance

The UF2 and Arduino C++ source are the existing integrated 0.6.0 build. The binary
was not rebuilt during this packaging step:

- RP2040 Pico, Arduino CLI 1.2.2, Arduino-Pico 6.3.0, 125 MHz.
- ArduinoJson 7.4.2, Adafruit BNO055 1.6.4, BMP3XX 2.1.6, BusIO 1.17.4 and
  Unified Sensor 1.1.15. Servo/SD/SPI/Wire from the core.
- Prior build: 128,540 program bytes; 12,308 bytes global RAM. The original host
  build omitted the compiler's `-pipe` option.
- The actual-sketch native harness previously passed with real ArduinoJson and
  peripheral doubles, covering servo pulses, sensor/log schedules, motor timeout,
  stop, USB loss, bad commands and re-enable. It was not rerun during packaging.
  To rerun: `python3 rover_ros2/tests/run_firmware_test.py --arduino-json PATH/src`.

## Remaining checks

The PowerShell 5 scripts were statically reviewed; this Linux environment cannot
execute them. ROS Jazzy/colcon, live DDS and GUI rendering were not tested here.
No physical Pico, Orange Pi, servo, motor, sensor or SD card was connected here.

Team telemetry previously confirmed USB status and temperature/pressure/altitude
packets. SD mounting failed and acceleration reported three zeros. Actual motion,
power capacity, direction, zero, travel, SD logging and sensor accuracy still need
testing on the rover.

The four servo channels boot stopped. Their provisional range is ±10°, mapped
to 1400–1600 µs. Zero means 1500 µs, not a measured angle; initial enable can move
a misaligned mechanism. Stop detaches pulses and cannot guarantee that a loaded
arm holds position.

The receiver preserves complete lines; it cannot recreate bytes lost to competing
readers or USB/firmware faults. Serial locking is advisory. Repeated malformed
frames after startup still require checking ownership and firmware output.
