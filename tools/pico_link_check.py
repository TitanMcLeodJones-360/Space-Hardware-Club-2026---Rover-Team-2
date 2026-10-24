#!/usr/bin/env python3
"""Read real Pico telemetry without enabling outputs. Stop ROS bridge first."""
import argparse
import json
import math
import time

FIELDS = ('temperature', 'pressure', 'accel_x', 'accel_y', 'accel_z', 'altitude')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port')
    parser.add_argument('--seconds', type=float, default=10)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 1 <= args.seconds <= 300:
        parser.error('--seconds must be between 1 and 300')
    try:
        import serial
    except ImportError:
        parser.error('Install pyserial (Ubuntu: sudo apt install python3-serial)')
    status_seen = False
    real_samples = 0
    complete_samples = 0
    first_rows = None
    last_rows = None
    last_status = {}
    pending = b''
    with serial.Serial(args.port, 115200, timeout=0.1, write_timeout=1) as link:
        deadline = time.monotonic() + args.seconds
        last_query = 0.0
        while time.monotonic() < deadline:
            if time.monotonic() - last_query >= 1:
                link.write(b'{"command":"STATUS"}\n')
                last_query = time.monotonic()
            pending += link.read(min(max(link.in_waiting, 1), 4096))
            if len(pending) > 16384:
                raise RuntimeError('Oversized serial line; check firmware/baud')
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                try:
                    packet = json.loads(line.decode('utf-8'))
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(packet, dict):
                    continue
                print(json.dumps(packet, allow_nan=False))
                if packet.get('type') == 'status':
                    status_seen = True
                    last_status = packet
                    rows = packet.get('sd_rows')
                    if type(rows) is int:
                        if first_rows is None:
                            first_rows = rows
                        last_rows = rows
                if packet.get('type') == 'sensors' and packet.get('mode') == 'hardware':
                    real_samples += 1
                    values = packet.get('data', {})
                    if isinstance(values, dict) and all(
                        type(values.get(key)) in (int, float) and math.isfinite(values[key])
                        for key in FIELDS
                    ):
                        complete_samples += 1
    checks = {
        'status_received': status_seen,
        'imu_ready': last_status.get('imu_ready') is True,
        'bmp_ready': last_status.get('bmp_ready') is True,
        'sd_ready': last_status.get('sd_ready') is True,
        'real_sensor_packets': real_samples,
        'complete_sensor_packets': complete_samples,
        'sd_rows_increased': first_rows is not None and last_rows > first_rows,
    }
    print('CHECKS', json.dumps(checks))
    passed = (all(checks[k] for k in ('status_received', 'imu_ready', 'bmp_ready',
                                     'sd_ready', 'sd_rows_increased'))
              and complete_samples > 0)
    print('PASS' if passed else 'FAIL: inspect wiring, address, card, and received frames')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
