# Validation - 15 October 2026

## Results

- Full Arduino sketch compile and link: PASS; nonempty ELF, BIN and UF2 generated.
- Target: rp2040:rp2040:rpipico:freq=125 (standard RP2040 Pico, 125 MHz).
- UF2 structure/family/address validation: PASS; 559 blocks, RP2040 family 0xe48bff56.
- Compiled header files compared to delivered source: identical after removing Arduino's generated #line directives.
- Python bridge/protocol/message tests: 35 passed. They use ROS doubles, not a live ROS installation.
- Native C++ control/configuration tests: PASS in default output dry run, real motor-only configuration, and intentionally blocked uncalibrated-servo configuration. Includes stop, heartbeat expiry, motor expiry, re-enable, and millis wraparound cases.
- All 13 assigned signal GPIOs compared with the extracted schematic nets: PASS.
- Both firmware source copies in the package: identical.
- Python source syntax compilation and serial checker help: PASS.

## Toolchain

Arduino CLI 1.2.2; Earle Philhower RP2040 core 6.3.0; ArduinoJson 7.4.2; Adafruit BNO055 1.6.4; Adafruit BMP3XX Library 2.1.6; BusIO 1.17.4; Unified Sensor 1.1.15. Wire/SPI/SD/Servo are bundled with that core.

The container compiler runner initially produced empty object files. The successful build used the stable CLI and omitted the `-pipe` compiler transport flag from the local installed core's platform settings. No dependency source changes were required. Existing unused-parameter warnings were in the Adafruit BMP3XX library. No firmware compile errors remained.

Build command (after that container-specific launcher adjustment):

```bash
arduino-cli compile --jobs 2 --fqbn rp2040:rp2040:rpipico:freq=125 --warnings all pico_arduino/rover_pico
```

## What these checks do not establish

No Pico, sensors, SD card, motor, servo, physical pull-stop, or operator network was accessible here. No physical operation, measured timing, successful hardware packet transfer, valid SD file capture, or live ROS/colcon build is claimed. The real hardware checks in README.md remain to be performed. Servo layout/coupling and calibration remain unconfirmed and are guarded in config.h.

## Source identity

- Uploaded Electrical Stuff ZIP SHA-256: `b12891d8444db9535bdb8de3f69544f307e6c091e45b62a175788ba8454c0f29`
- Main schematic from embedded archive `_5.7z` SHA-256: `7cd08d19ad06f47938739d87bace9eb700670c3acf0fa6de6ac42466ee0a5da8`
- Prebuilt default bench UF2 SHA-256: `894521c4ef95d587d37c53f40dd50e15a1bca5e8a27a3c70c6bb437de9a732de`

The prebuilt UF2 enables real sensing/logging and disables actuator output. It is specifically for the standard RP2040 Pico. Rebuild from source for another board or any configuration changes.
