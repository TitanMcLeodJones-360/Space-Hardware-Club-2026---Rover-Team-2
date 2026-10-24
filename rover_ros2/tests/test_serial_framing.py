"""Receive framing and bridge regressions; no ROS installation or hardware needed."""
import json
import os
from pathlib import Path
import random
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rover_control.serial_framing import LineBuffer
import test_controls as controls


class FramingTests(unittest.TestCase):
    def test_every_split_boundary_including_crlf_and_utf8(self):
        packet = '{"note":"Température","ready":true}\r\n'.encode()
        for offset in range(len(packet) + 1):
            reader = LineBuffer()
            frames = reader.feed(packet[:offset]) + reader.feed(packet[offset:])
            self.assertEqual(frames, [packet[:-2]])

    def test_multiple_lines_and_empty_lines(self):
        reader = LineBuffer()
        self.assertEqual(reader.feed(b'\n\r\n{"n":1}\n{"n":2}\n{"n":'),
                         [b'{"n":1}', b'{"n":2}'])
        self.assertEqual(reader.feed(b'3}\n'), [b'{"n":3}'])

    def test_size_limit_applies_to_each_line_not_entire_read(self):
        reader = LineBuffer(8)
        self.assertEqual(reader.feed(b'12345678\n' * 100), [b'12345678'] * 100)
        self.assertEqual(reader.dropped_lines, 0)

    def test_overflow_discards_through_newline_and_keeps_following_frame(self):
        reader = LineBuffer(8)
        self.assertEqual(reader.feed(b'123456789'), [])
        self.assertLessEqual(len(reader.pending), 8)
        self.assertEqual(reader.feed(b'"ready":true\n{}\n'), [b'{}'])
        self.assertEqual(reader.dropped_lines, 1)
        self.assertFalse(reader.discarding)

    def test_random_chunking_preserves_order_and_contents(self):
        packets = [json.dumps({"n": n, "note": "Pico"}).encode() for n in range(200)]
        wire = b'\n'.join(packets) + b'\n'
        reader = LineBuffer()
        received = []
        rng = random.Random(42)
        while wire:
            size = rng.randrange(1, 150)
            received.extend(reader.feed(wire[:size]))
            wire = wire[size:]
        self.assertEqual(received, packets)


class SerialBridgeTests(unittest.TestCase):
    # Reuse the existing ROS message doubles and clock, without duplicating tests.
    setUpClass = classmethod(controls.BridgeTests.setUpClass.__func__)
    tearDownClass = classmethod(controls.BridgeTests.tearDownClass.__func__)
    setUp = controls.BridgeTests.setUp
    tearDown = controls.BridgeTests.tearDown
    serial_bridge = controls.BridgeTests.serial_bridge
    message = controls.BridgeTests.message

    status = b'{"mode":"hardware","ready":true,"enabled":false}\n'

    def test_complete_first_status_is_accepted(self):
        bridge, serial = self.serial_bridge()
        serial.incoming = self.status
        bridge.poll()
        self.assertTrue(bridge.pico_online())

    def test_first_sensor_packet_is_published(self):
        bridge, serial = self.serial_bridge()
        serial.incoming = b'{"type":"sensors","mode":"hardware","data":{"temperature":20}}\n'
        bridge.poll()
        self.assertEqual(len(bridge.sensor_publisher.messages), 1)

    def test_startup_tail_and_later_malformed_lines_do_not_block_good_status(self):
        bridge, serial = self.serial_bridge()
        serial.incoming = b'"hardware","ready":true}\r\n' + self.status
        bridge.poll()
        self.assertTrue(bridge.pico_online())
        self.now += 2
        serial.incoming = b'{broken JSON}\n'
        bridge.poll()
        self.assertFalse(bridge.pico_online())
        serial.incoming = self.status
        bridge.poll()
        self.assertTrue(bridge.pico_online())

    def test_bytewise_status_does_not_refresh_until_newline(self):
        bridge, serial = self.serial_bridge()
        for byte in self.status[:-1]:
            serial.incoming = bytes([byte])
            bridge.poll()
            self.assertIsNone(bridge.last_pico_status)
        serial.incoming = b'\n'
        bridge.poll()
        self.assertTrue(bridge.pico_online())

    def test_oversized_line_cannot_turn_its_tail_into_a_status(self):
        bridge, serial = self.serial_bridge()
        serial.incoming = b'x' * 9000 + self.status
        while serial.incoming:
            bridge.poll()
        self.assertIsNone(bridge.last_pico_status)
        serial.incoming = self.status
        bridge.poll()
        self.assertTrue(bridge.pico_online())
        self.assertEqual(bridge.rx_lines.dropped_lines, 1)

    def test_malformed_and_invalid_unicode_do_not_publish_or_enable(self):
        bridge, serial = self.serial_bridge()
        serial.incoming = b'\xff\n{"ready":\n'
        bridge.poll()
        self.assertIsNone(bridge.last_pico_status)
        self.assertEqual(bridge.sensor_publisher.messages, [])
        self.assertNotIn(b'ARM_ENABLE', b''.join(serial.writes))

    def test_open_is_nonblocking_and_requests_exclusive_access(self):
        serial = controls.FakeSerial()
        controls.FakeNode.overrides = {"dry_run": False, "serial_port": "/dev/test"}
        with patch.dict(sys.modules, serial=type("SerialModule", (), {})()):
            with patch("serial.Serial", return_value=serial, create=True) as opened:
                self.bridge_module.ArmBridge()
                self.assertEqual(opened.call_args.kwargs["timeout"], 0)
                self.assertTrue(opened.call_args.kwargs["exclusive"])


@unittest.skipUnless(os.name == "posix", "PTY test needs POSIX")
class RealSerialTests(unittest.TestCase):
    def test_pty_split_frames_and_exclusive_open(self):
        try:
            import serial
        except ImportError:
            self.skipTest("Install python3-serial for the real pySerial/PTY check")
        import pty
        master, slave = pty.openpty()
        try:
            with serial.Serial(os.ttyname(slave), 115200, timeout=0,
                               write_timeout=0.1, exclusive=True) as link:
                with self.assertRaises(serial.SerialException):
                    serial.Serial(os.ttyname(slave), 115200, exclusive=True)
                reader = LineBuffer()
                received = []
                for chunk in (b'{"ready":', b'true}', b'\n{"n":2}\n'):
                    os.write(master, chunk)
                    deadline = time.monotonic() + 1
                    while link.in_waiting < len(chunk) and time.monotonic() < deadline:
                        time.sleep(0.001)
                    received.extend(reader.feed(link.read(link.in_waiting)))
                self.assertEqual(received, [b'{"ready":true}', b'{"n":2}'])
        finally:
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
