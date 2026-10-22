"""Controller state machine; no ROS, Qt, USB, or Windows dependencies."""
import math
from .protocol import AXES, is_number


class XboxControl:
    # SDL game_controller_node order; Windows helper emits the same layout.
    START, STOP, BACK, RB, UP, DOWN = 6, 1, 4, 10, 11, 12
    INPUT_TIMEOUT = 0.30
    STATUS_TIMEOUT = 0.60
    DEADZONE = 0.15
    SERVO_RATE = 10.0  # degrees/s; Axis3B uses half this rate.
    MOTOR_LIMIT = 30.0

    def __init__(self):
        self.axes = (0.0,) * 6
        self.buttons = (0,) * 15
        self.last_input = self.last_status = self.last_tick = None
        self.status = {}
        self.targets = {}
        self.neutral_seen = False
        self.armed = False
        self.pending_enable = False
        self.enable_deadline = 0.0
        self.enable_requested = False
        self.stop_pending = False
        self.last_motor = 0.0
        self.note = 'Waiting for controller; release buttons and center sticks'

    def input_fresh(self, now):
        return self.last_input is not None and 0 <= now - self.last_input < self.INPUT_TIMEOUT

    def status_fresh(self, now):
        return self.last_status is not None and 0 <= now - self.last_status < self.STATUS_TIMEOUT

    def neutral(self):
        return (all(abs(v) <= self.DEADZONE for v in self.axes[:4])
                and not self.buttons[self.UP] and not self.buttons[self.DOWN])

    def stop(self, reason):
        self.stop_pending = True
        self.armed = self.pending_enable = self.enable_requested = False
        self.neutral_seen = False
        self.last_motor = 0.0
        self.note = reason + '; release buttons, center sticks, then RB + Start'

    def disconnected(self):
        if self.last_input is not None or self.armed or self.pending_enable:
            self.stop('Controller disconnected')
        self.last_input = None

    def receive(self, axes, buttons, now):
        try:
            valid = (math.isfinite(now) and len(axes) >= 6 and len(buttons) >= 15
                     and all(is_number(v) and -1.01 <= v <= 1.01 for v in axes[:6])
                     and all(type(b) is int and b in (0, 1) for b in buttons[:15]))
        except (TypeError, ValueError):
            valid = False
        if not valid:
            self.stop('Invalid controller input')
            self.last_input = None
            return
        was_fresh = self.input_fresh(now)
        if not was_fresh:
            if self.last_input is not None or self.armed or self.pending_enable:
                self.stop('Controller input timed out')
            self.neutral_seen = False
        previous = self.buttons if was_fresh else tuple(buttons)
        self.axes, self.buttons = tuple(axes[:6]), tuple(buttons[:15])
        self.last_input = now
        if self.buttons[self.STOP] or self.buttons[self.BACK]:
            self.stop('Operator stop')
            return
        if previous[self.RB] and not self.buttons[self.RB]:
            self.stop('RB released')
            return
        if self.neutral() and not any(self.buttons):
            self.neutral_seen = True
            self.note = 'Controller ready; hold RB and press Start with sticks centered'
        if self.buttons[self.START] and not previous[self.START]:
            if self.neutral_seen and self.neutral() and self.buttons[self.RB]:
                self.enable_requested = True
            else:
                self.note = 'Enable blocked: release buttons and center sticks first'

    def receive_status(self, status, now):
        self.status, self.last_status = status, now
        if not self.armed:
            self.targets = dict(status.get('targets', {}))

    def heartbeat_allowed(self, now):
        return (self.input_fresh(now) and self.buttons[self.RB]
                and not self.buttons[self.STOP] and not self.buttons[self.BACK]
                and (self.neutral_seen or self.armed or self.pending_enable))

    @staticmethod
    def scaled(value):
        if abs(value) <= XboxControl.DEADZONE:
            return 0.0
        return math.copysign((min(abs(value), 1.0) - XboxControl.DEADZONE)
                             / (1.0 - XboxControl.DEADZONE), value)

    def step(self, now):
        dt = 0.0 if self.last_tick is None else max(0.0, min(now - self.last_tick, 0.1))
        self.last_tick = now
        # A stalled operator loop needs a fresh enable even if input callbacks resume.
        if not self.input_fresh(now):
            if self.armed or self.pending_enable:
                self.stop('Controller input timed out')
        if not self.status_fresh(now) or not self.status.get('ready'):
            if self.armed or self.pending_enable or self.enable_requested:
                self.stop('Arm status unavailable')
        if self.stop_pending:
            self.stop_pending = False
            return [{'command': 'STOP_ALL'}, {'motor': 'DC', 'speed': 0.0}]
        if self.enable_requested:
            self.enable_requested = False
            if (self.heartbeat_allowed(now) and self.neutral() and self.status_fresh(now)
                    and self.status.get('ready')):
                self.armed = self.pending_enable = True
                self.enable_deadline = now + 1.0
                self.targets = dict(self.status.get('targets', {}))
                self.note = 'Enable requested; waiting for arm acknowledgement'
                return [{'command': 'ARM_ENABLE'}]
        if not self.armed:
            return []
        if not self.buttons[self.RB]:
            self.stop('RB released')
            return self.step(now)
        if self.pending_enable:
            if self.status.get('enabled'):
                self.pending_enable = False
                self.targets = dict(self.status.get('targets', {}))
                self.note = 'Xbox control active; hold RB to move'
            elif now >= self.enable_deadline:
                self.stop('Arm did not enable')
                return self.step(now)
            return []
        if not self.status.get('enabled'):
            self.stop('Arm stopped')
            return self.step(now)
        commands = []
        rates = {'Axis1': self.scaled(self.axes[1]),
                 'Axis2': self.scaled(self.axes[3]),
                 'Axis3A': -self.scaled(self.axes[2]),
                 'Axis3B': 0.5 * (self.buttons[self.UP] - self.buttons[self.DOWN])}
        for name in AXES:
            if name not in self.targets or name not in self.status.get('limits', {}):
                continue
            low, high = self.status['limits'][name]
            target = min(high, max(low, self.targets[name] + rates[name] * self.SERVO_RATE * dt))
            if abs(target - self.targets[name]) > 1e-6:
                self.targets[name] = target
                commands.append({'axis': name, 'angle': target})
        limit = min(self.MOTOR_LIMIT, abs(self.status.get('motor_limit', 0)))
        speed = -self.scaled(self.axes[0]) * limit if self.status.get('motor_ready') else 0.0
        if speed != 0.0 or self.last_motor != 0.0:
            commands.append({'motor': 'DC', 'speed': speed})
        self.last_motor = speed
        return commands
