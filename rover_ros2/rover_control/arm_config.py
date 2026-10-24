# Computer-side simulation mirrors the integrated Pico profile.
# Physical GPIO/pulse settings remain in pico/rover_pico/config.h.
DRY_RUN = True
try:
    from .protocol import AXES
except ImportError:
    from protocol import AXES
JOINTS = AXES
SIM_LIMITS = {name: (-10.0, 10.0) for name in JOINTS}
SIM_HOME = {name: 0.0 for name in JOINTS}
