# Settings for the computer-side simulation only.
# Pico GPIO and calibration settings are in pico/rover_pico/config.h.
DRY_RUN = True
try:
    from .protocol import AXES
except ImportError:
    from protocol import AXES
JOINTS = AXES

# Preview-only defaults for still-uncalibrated channels; physical limits live on Pico.
SIM_LIMITS = {name: (0.0, 180.0) for name in JOINTS}
SIM_LIMITS["Axis3A"] = (-70.0, 70.0)
SIM_HOME = {name: 90.0 for name in JOINTS}
SIM_HOME["Axis3A"] = 0.0
