#!/usr/bin/env bash
# Unit tests use ROS/Qt doubles; pySerial enables the real POSIX PTY check.
set -eo pipefail
rover_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python3 -m unittest discover -s "$rover_repo/rover_ros2/tests" -p 'test_*.py' -v
rover_test_dir=$(mktemp -d)
trap 'rm -rf -- "$rover_test_dir"' EXIT
for rover_profile in hardware dry_run motor_only; do
    rover_defines=()
    case "$rover_profile" in
        dry_run) rover_defines=(-DROVER_DRY_RUN=1) ;;
        motor_only) rover_defines=(-DROVER_USE_SERVOS=0) ;;
    esac
    g++ -std=c++17 -Wall -Wextra -Werror "${rover_defines[@]}" \
        "$rover_repo/rover_ros2/tests/test_pico_control.cpp" -o "$rover_test_dir/$rover_profile"
    "$rover_test_dir/$rover_profile"
done
