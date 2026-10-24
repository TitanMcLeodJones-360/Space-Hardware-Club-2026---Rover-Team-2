import ctypes
import importlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rover_control.xbox_control import XboxControl
from rover_control.xbox_udp import XboxUDP
from test_controls import FakeNode, FakeSerial, fake_ros_modules


def status(enabled=False):
    return {'ready': True, 'enabled': enabled, 'motor_ready': True, 'motor_limit': 30.0,
            'targets': {'Axis1': 90.0, 'Axis2': 90.0, 'Axis3A': 0.0, 'Axis3B': 90.0},
            'limits': {'Axis1': [0, 180], 'Axis2': [0, 180], 'Axis3A': [-70, 70], 'Axis3B': [0, 180]}}


def buttons(*indices):
    result = [0] * 15
    for i in indices:
        result[i] = 1
    return result


class XboxLogicTests(unittest.TestCase):
    def setUp(self):
        self.c = XboxControl()
        self.now = 1.0
        self.c.receive_status(status(), self.now)

    def frame(self, held=(), axes=None, elapsed=0.05):
        self.now += elapsed
        self.c.receive([0.0] * 6 if axes is None else axes, buttons(*held), self.now)
        self.c.receive_status(status(self.c.armed and not self.c.pending_enable), self.now)
        return self.c.step(self.now)

    def enable(self):
        self.frame()
        self.frame((10,))
        self.assertEqual(self.frame((10, 6)), [{'command': 'ARM_ENABLE'}])
        self.now += 0.05
        self.c.receive_status(status(True), self.now)
        self.c.receive([0.] * 6, buttons(10), self.now)
        self.c.step(self.now)
        self.assertTrue(self.c.armed)
        self.assertFalse(self.c.pending_enable)

    def test_held_start_at_connect_cannot_enable(self):
        self.assertEqual(self.frame((10, 6)), [])
        self.assertFalse(self.c.armed)

    def test_enable_requires_released_buttons_and_centered_sticks(self):
        self.frame()
        self.assertEqual(self.frame((10, 6), [0, 1, 0, 0, 0, 0]), [])
        self.assertFalse(self.c.armed)
        self.assertNotIn({'command': 'ARM_ENABLE'}, self.frame((6,)))
        self.assertFalse(self.c.armed)

    def test_movement_waits_for_arm_acknowledgement(self):
        self.frame()
        self.frame((10,))
        self.frame((10, 6))
        self.assertTrue(self.c.pending_enable)
        self.assertEqual(self.frame((10,), [1, 1, 1, 1, 0, 0]), [])

    def test_release_stops_and_requires_fresh_enable(self):
        self.enable()
        result = self.frame()
        self.assertEqual(result[0], {'command': 'STOP_ALL'})
        self.assertFalse(self.c.heartbeat_allowed(self.now))
        self.assertFalse(self.c.armed)
        self.assertEqual(self.frame((10,)), [])
        self.assertEqual(self.frame((10,)), [])

    def test_b_and_back_stop(self):
        for key in (1, 4):
            self.setUp()
            self.enable()
            self.assertEqual(self.frame((10, key))[0], {'command': 'STOP_ALL'})
            self.assertFalse(self.c.armed)

    def test_stale_input_stops_and_reconnect_is_not_enable(self):
        self.enable()
        result = self.c.step(self.now + 0.31)
        self.assertEqual(result[0], {'command': 'STOP_ALL'})
        self.now += 0.31
        self.assertNotIn({'command': 'ARM_ENABLE'}, self.frame((10, 6)))
        self.assertFalse(self.c.armed)

    def test_explicit_unplug_and_invalid_input_stop(self):
        self.enable()
        self.c.disconnected()
        self.assertEqual(self.c.step(self.now)[0], {'command': 'STOP_ALL'})
        for axes, b in [(None, buttons()), ([float('nan')] * 6, buttons()),
                        ([2.] * 6, buttons()), ([0.] * 6, [1]),
                        ([True] * 6, buttons())]:
            self.c.receive(axes, b, self.now)
            self.assertEqual(self.c.step(self.now)[0], {'command': 'STOP_ALL'})

    def test_deadzone_and_rate_limit(self):
        self.enable()
        result = self.frame((10,), [0.1] * 6)
        self.assertEqual(result, [])
        result = self.frame((10,), [0, 1, -1, 1, 0, 0])
        commands = {p['axis']: p['angle'] for p in result if 'axis' in p}
        self.assertAlmostEqual(commands['Axis1'], 90.5)
        self.assertAlmostEqual(commands['Axis2'], 90.5)
        self.assertAlmostEqual(commands['Axis3A'], 0.5)

    def test_both_signs_of_axis3a_are_clamped(self):
        self.enable()
        for target, stick, expected in [(69.9, -1, 70), (-69.9, 1, -70)]:
            self.c.targets['Axis3A'] = target
            commands = self.frame((10,), [0, 0, stick, 0, 0, 0])
            self.assertEqual(next(p['angle'] for p in commands if p.get('axis') == 'Axis3A'), expected)

    def test_motor_refresh_zero_release_and_limit(self):
        self.enable()
        for _ in range(2):
            result = self.frame((10,), [-1, 0, 0, 0, 0, 0])
            self.assertIn({'motor': 'DC', 'speed': 30.0}, result)
        self.assertIn({'motor': 'DC', 'speed': 0.0}, self.frame((10,)))

    def test_motor_disabled_and_unavailable_joint_not_commanded(self):
        self.enable()
        s = status(True)
        s['motor_ready'] = False
        s['targets'].pop('Axis3B')
        s['limits'].pop('Axis3B')
        self.c.receive_status(s, self.now)
        self.c.receive([-1, 0, 0, 0, 0, 0], buttons(10, 11), self.now)
        self.assertEqual(self.c.step(self.now), [])

    def test_status_loss_and_enable_timeout_stop(self):
        self.enable()
        self.c.last_status = self.now - 1
        self.assertEqual(self.c.step(self.now)[0], {'command': 'STOP_ALL'})
        self.setUp()
        self.frame()
        self.frame((10,))
        self.frame((10, 6))
        for _ in range(21):
            last = self.frame((10,))
        self.assertFalse(self.c.armed)
        self.assertTrue(any(p.get('command') == 'STOP_ALL' for p in last) or self.c.note.startswith('Arm did not'))


class UDPTests(unittest.TestCase):
    def setUp(self):
        self.receiver = XboxUDP(0)
        self.sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = self.receiver.socket.getsockname()

    def tearDown(self):
        self.receiver.close()
        self.sender.close()

    def send(self, session='abc', seq=1, connected=True):
        p = {'version': 1, 'session': session, 'seq': seq, 'connected': connected,
             'axes': [0] * 6, 'buttons': buttons()}
        self.sender.sendto(json.dumps(p).encode(), self.addr)

    def test_loopback_frame_and_duplicates(self):
        self.send()
        self.assertTrue(self.receiver.poll()['connected'])
        self.send()
        self.assertIsNone(self.receiver.poll())
        self.send(seq=2)
        self.assertTrue(self.receiver.poll()['connected'])

    def test_restart_stops_even_if_followed_by_new_session_data(self):
        self.send()
        self.receiver.poll()
        self.send(session='new', seq=1)
        self.send(session='new', seq=2)
        self.assertFalse(self.receiver.poll()['connected'])
        self.send(session='new', seq=3)
        self.assertTrue(self.receiver.poll()['connected'])
        self.send(seq=5)
        self.assertIsNone(self.receiver.poll())

    def test_bad_and_disconnected_frames_stop(self):
        self.sender.sendto(b'bad json', self.addr)
        self.assertFalse(self.receiver.poll()['connected'])
        self.send(connected=False)
        self.assertFalse(self.receiver.poll()['connected'])


class WindowsMappingTests(unittest.TestCase):
    def test_xinput_layout_and_directions(self):
        p = ROOT.parent / 'tools/xbox_windows.py'
        spec = importlib.util.spec_from_file_location('xinput_helper_test', p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(ctypes.sizeof(mod.Gamepad), 12)
        self.assertEqual(ctypes.sizeof(mod.State), 16)
        pad = mod.Gamepad(buttons=0x0200 | 0x0010 | 0x0001, left_x=32767, left_y=-32768)
        axes, b = mod.controls(pad)
        self.assertEqual(axes[:2], [-1.0, -1.0])
        self.assertEqual([i for i, value in enumerate(b) if value], [6, 10, 11])


class XboxROSIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.modules = patch.dict(sys.modules, fake_ros_modules())
        self.modules.start()
        self.now = 10.
        self.clock = patch('time.monotonic', lambda: self.now)
        self.clock.start()
        FakeNode.overrides = {'use_xbox': True}
        self.module = importlib.import_module('rover_control.ground_station_ros')
        self.gui = self.module.GroundStationROS(Mock())
        self.gui.connected = lambda: True
        self.gui.xbox.receive_status(status(), self.now)

    def tearDown(self):
        self.clock.stop()
        self.modules.stop()
        FakeNode.overrides = {}

    def joy(self, held=(), axes=None):
        self.now += 0.05
        self.gui.receive_joy(types.SimpleNamespace(axes=[0.] * 6 if axes is None else axes,
                                                   buttons=buttons(*held)))

    def test_mouse_motion_rejected_but_stop_allowed(self):
        with self.assertRaises(ValueError):
            self.gui.send_command({'axis': 'Axis1', 'angle': 95})
        self.gui.send_command('STOP_ALL')
        self.assertGreaterEqual(len(self.gui.stop_publisher.messages), 2)

    def test_controller_enable_heartbeat_motion_stop(self):
        self.joy()
        self.joy((10,))
        self.gui.send_heartbeat()
        self.assertTrue(self.gui.heartbeat.messages[-1].data)
        self.joy((10, 6))
        self.assertEqual(len(self.gui.enable_publisher.messages), 1)
        self.gui.xbox.receive_status(status(True), self.now)
        self.joy((10,))
        self.joy((10,), [-1., 0., -1., 0., 0., 0.])
        self.assertEqual(self.gui.motor_publisher.messages[-1].data, 30.0)
        self.assertEqual(self.gui.joint_publisher.messages[-1].joint, 'Axis3A')
        self.joy()
        count = len(self.gui.heartbeat.messages)
        self.gui.send_heartbeat()
        self.assertEqual(len(self.gui.heartbeat.messages), count)
        self.assertGreaterEqual(len(self.gui.stop_publisher.messages), 2)

    def test_driver_timeout_gates_heartbeat_and_sends_stop(self):
        self.joy()
        self.joy((10,))
        self.joy((10, 6))
        self.now += 0.31
        count = len(self.gui.heartbeat.messages)
        self.gui.controller_tick()
        self.gui.send_heartbeat()
        self.assertEqual(len(self.gui.heartbeat.messages), count)
        self.assertFalse(self.gui.xbox.armed)
        self.assertGreaterEqual(len(self.gui.stop_publisher.messages), 2)

    def test_windows_udp_to_ros_bridge_serial_with_signed_angle(self):
        FakeNode.overrides = {'use_xbox': True, 'xbox_source': 'windows', 'xbox_port': 0}
        gui = self.module.GroundStationROS(Mock())
        gui.connected = lambda: True
        bridge_module = importlib.import_module('rover_control.arm_bridge')
        serial = FakeSerial()
        FakeNode.overrides = {'dry_run': False, 'serial_port': '/dev/test'}
        with patch.dict(sys.modules, serial=types.SimpleNamespace(Serial=lambda *a, **k: serial)):
            bridge = bridge_module.ArmBridge()
        serial.incoming = b'{"type":"status","mode":"simulation","ready":true,"enabled":false}\n'
        bridge.poll()
        gui.xbox.receive_status(status(), self.now)
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        seq = 0
        def frame(held=(), axes=None):
            nonlocal seq
            seq += 1
            self.now += 0.05
            packet = {'version': 1, 'session': 'integration', 'seq': seq, 'connected': True,
                      'axes': [0.] * 6 if axes is None else axes, 'buttons': buttons(*held)}
            sender.sendto(json.dumps(packet).encode(), gui.xbox_udp.socket.getsockname())
            gui.controller_tick()
        try:
            frame()
            frame((10,))
            frame((10, 6))
            bridge.receive_heartbeat(gui.heartbeat.messages[-1])
            bridge.receive_enable(gui.enable_publisher.messages[-1])
            self.assertEqual(json.loads(serial.writes[-1]), {'command': 'ARM_ENABLE'})
            ack = dict(status(True), type='status', mode='simulation')
            serial.incoming = (json.dumps(ack) + '\n').encode()
            bridge.poll()
            bridge.publish_status()
            gui.receive_status(bridge.publisher.messages[-1])
            frame((10,))
            frame((10,), [0, 0, 1, 0, 0, 0])
            bridge.receive_joint(gui.joint_publisher.messages[-1])
            packet = json.loads(serial.writes[-1])
            self.assertEqual(packet['axis'], 'Axis3A')
            self.assertLess(packet['angle'], 0)
            frame()
            bridge.receive_stop(gui.stop_publisher.messages[-1])
            self.assertEqual(json.loads(serial.writes[-1]), {'command': 'STOP_ALL'})
        finally:
            sender.close()
            gui.close()
