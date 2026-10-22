#!/usr/bin/env python3
"""Read an Xbox controller in Windows and send to mirrored WSL over loopback.
Standard library only. Keep this running while the Xbox ground station is open.
"""
import argparse
import ctypes
import json
import socket
import sys
import time
import uuid


class Gamepad(ctypes.Structure):
    _fields_ = [('buttons', ctypes.c_uint16), ('left_trigger', ctypes.c_uint8),
                ('right_trigger', ctypes.c_uint8), ('left_x', ctypes.c_int16),
                ('left_y', ctypes.c_int16), ('right_x', ctypes.c_int16),
                ('right_y', ctypes.c_int16)]


class State(ctypes.Structure):
    _fields_ = [('packet', ctypes.c_uint32), ('gamepad', Gamepad)]


def normalized(value):
    return max(-1.0, min(1.0, value / (32767.0 if value >= 0 else 32768.0)))


def controls(pad):
    # Match ROS SDL conventions: left and up positive. Triggers are unused.
    axes = [-normalized(pad.left_x), normalized(pad.left_y),
            -normalized(pad.right_x), normalized(pad.right_y),
            -pad.left_trigger / 255.0, -pad.right_trigger / 255.0]
    masks = (0x1000, 0x2000, 0x4000, 0x8000, 0x0020, 0, 0x0010,
             0x0040, 0x0080, 0x0100, 0x0200, 0x0001, 0x0002, 0x0004, 0x0008)
    return axes, [int(bool(pad.buttons & mask)) for mask in masks]


def get_xinput():
    if sys.platform != 'win32':
        raise RuntimeError('Run this helper in Windows PowerShell, not Ubuntu/WSL')
    for name in ('xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll'):
        try:
            dll = ctypes.WinDLL(name)
            get_state = dll.XInputGetState
            get_state.argtypes = [ctypes.c_uint32, ctypes.POINTER(State)]
            get_state.restype = ctypes.c_uint32
            return get_state
        except (OSError, AttributeError):
            continue
    raise RuntimeError('Windows XInput DLL not available')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=int, choices=range(4), default=0)
    parser.add_argument('--port', type=int, default=15002)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('--port must be between 1024 and 65535')
    get_state = get_xinput()
    session = uuid.uuid4().hex
    seq = 0
    previous = None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as link:
        def send(connected, axes=(), buttons=()):
            nonlocal seq
            seq += 1
            packet = {'version': 1, 'session': session, 'seq': seq,
                      'connected': connected, 'axes': axes, 'buttons': buttons}
            link.sendto(json.dumps(packet).encode('utf-8'), ('127.0.0.1', args.port))
        print('Xbox helper running. Connect controller by USB; Ctrl+C stops.')
        print('Ground station: xbox:=true xbox_source:=windows (mirrored WSL)')
        try:
            while True:
                state = State()
                connected = get_state(args.index, ctypes.byref(state)) == 0
                if connected != previous:
                    print('Controller connected' if connected else
                          'Controller disconnected/not found; check USB cable and index')
                    previous = connected
                if connected:
                    axes, buttons = controls(state.gamepad)
                    send(True, axes, buttons)
                else:
                    send(False)
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        finally:
            send(False)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
