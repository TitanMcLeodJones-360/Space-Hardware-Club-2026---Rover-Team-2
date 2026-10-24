#!/usr/bin/env python3
"""Compile actual firmware with peripheral doubles; requires g++ and ArduinoJson 7."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arduino-json', type=Path, required=True, help='ArduinoJson src directory')
    args = parser.parse_args()
    tests = Path(__file__).resolve().parent
    firmware = tests.parent / 'pico' / 'rover_pico'
    with tempfile.TemporaryDirectory(prefix='rover-firmware-test-') as folder:
        target = Path(folder)
        shutil.copytree(tests / 'firmware_stubs', target, dirs_exist_ok=True)
        for name in ('rover_pico.ino', 'config.h', 'control.h'):
            shutil.copy2(firmware / name, target / name)
        shutil.copy2(tests / 'test_pico_firmware.cpp', target)
        executable = target / 'test_firmware'
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-I' + str(target), '-I' + str(args.arduino_json),
                        str(target / 'test_pico_firmware.cpp'), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    main()
