# ROS bridge simulation. Hardware outputs live in pico/rover_pico/.
try:
    from . import arm_config as config
    from .protocol import validate_command
except ImportError:
    import arm_config as config
    from protocol import validate_command

class RoverArm:
    def __init__(self, dry_run=None):
        self.dry_run = config.DRY_RUN if dry_run is None else dry_run
        self.enabled = False
        self.ready = False
        self.angles = {}
        self.last_note = "Not set up"
        self.motor_speed = 0
        self.motor_updated = None

    def setup_servos(self):
        if self.dry_run:
            self.angles = {name: 90 for name in config.JOINTS}
            self.ready = True
            self.last_note = "Simulation ready; no hardware output"
            return self.status()

        raise ValueError("Physical outputs use the Arduino firmware on the Pico")

    def set_angle(self, joint, angle):
        if not self.enabled:
            raise ValueError("Arm stopped; press Enable arm first")
        low, high = 0, 180
        target = max(low, min(high, angle))
        self.angles[joint] = target

    def stop_all(self, reason="Stopped by operator"):
        self.enabled = False
        self.motor_speed = 0
        self.last_note = reason
        return self.status()

    def handle_command(self, request):
        try:
            request = validate_command(request)
            command = request.get("command")
            if command in ("STOP_ALL", "LINK_LOST"):
                return self.stop_all("Connection lost" if command == "LINK_LOST" else "Stopped by operator")
            if command in ("HEARTBEAT", "STATUS"):
                return self.status()
            if command == "ARM_ENABLE":
                if not self.ready:
                    raise ValueError("Arm is not configured")
                if not self.enabled:
                    self.enabled = True
                    for name, target in self.angles.items():
                        self.set_angle(name, target)
                self.last_note = "Arm enabled"
            elif "motor" in request:
                if request["speed"] != 0 and not self.enabled:
                    raise ValueError("Enable the arm before running the DC motor")
                if not self.dry_run:
                    raise ValueError("Use the Arduino firmware for the physical DC motor")
                import time
                self.motor_speed = max(-30, min(30, request["speed"]))
                self.motor_updated = time.monotonic()
                self.last_note = "DC motor target updated"
            elif "axis" in request:
                self.set_angle(request["axis"], request["angle"])
                self.last_note = "Target set: " + request["axis"]
            else:
                raise ValueError("Unsupported arm command")
            return self.status()
        except Exception as exc:
            self.stop_all("Command failed")
            result = self.status()
            result["error"] = str(exc)
            return result

    def status(self):
        return {
            "type": "status",
            "mode": "simulation" if self.dry_run else "hardware",
            "ready": self.ready,
            "enabled": self.enabled,
            "targets": dict(self.angles),
            "limits": {name: [0, 180] for name in config.JOINTS},
            "motor_ready": self.dry_run,
            "motor_speed": self.motor_speed,
            "motor_limit": 30,
            "note": self.last_note,
        }

if __name__ == "__main__":
    arm = RoverArm(dry_run=True)
    arm.setup_servos()
    for command in ("ARM_ENABLE", {"axis": "Base", "angle": 95},
                    {"axis": "Gripper", "angle": 120}, "STOP_ALL"):
        print(arm.handle_command(command))
