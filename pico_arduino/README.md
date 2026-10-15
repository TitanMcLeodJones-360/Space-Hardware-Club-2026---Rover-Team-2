# Pico firmware

Open `rover_pico/rover_pico.ino`. Keep its five files together.

Read the package's top-level README.md for the pin table, upload/install instructions, bench test, and remaining mechanical calibration. The hardware wiring comes from the main sheet in schematic archive `_5.7z`.

Defaults read real BNO055/BMP388 sensors on Wire1 GP26/27 and log to SPI0 SD on GP16/17/18/19. DRY_RUN prevents all actuator signals. The four servo channel labels match the schematic, and their motion stays disabled pending mechanical layout and measured calibration.

This is Arduino C++ for Earle Philhower's Pico core, not MicroPython or Arduino Mbed. The duplicate firmware under rover_ros2/pico/rover_pico is identical to this copy. Update both copies if making later source changes.
