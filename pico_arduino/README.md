# Integrated Pico firmware

Use `firmware/Pico_RP2040_Integrated.uf2` from the repository root on a standard
RP2040 Pico. Source: `rover_pico/`; the copy under `rover_ros2/pico/rover_pico` is
identical. Sensors, SD logging, four servos and the TB6612 DC motor run together.
Outputs start disabled and require the GUI's Enable arm command plus heartbeats.

All four startup targets are 0 degrees, mapped provisionally to 1500 us. Initial
software travel is +/-10 degrees (1400..1600 us), with 5 degree/second ramping after
enable. Actual joint zero/direction/travel still require hardware verification;
these values are not measured feedback. First enable can reposition the arm if
its mechanical zero does not match electrical center.

See [the installation guide](../README.md) for the pin table, flashing, Orange Pi
setup, laptop GUI, logging checks, and stop behavior. Rebuild with
`bash tools/build_pico.sh` from the repository root after updating calibration.
