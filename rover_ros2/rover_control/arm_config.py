# Settings for the computer-side simulation only.
# Pico GPIO and calibration settings are in pico/rover_pico/config.h.
DRY_RUN = True
try:
    from .protocol import AXES
except ImportError:
    from protocol import AXES
JOINTS = AXES
