#!/usr/bin/env bash
# Run on Orange Pi or laptop Ubuntu/WSL; uses this repository's packages.
set -eo pipefail
rover_repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
rover_workspace=${1:-"$HOME/rover_ws"}
if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
    echo "ROS 2 Jazzy is missing at /opt/ros/jazzy. Install/source ROS first." >&2
    exit 1
fi
source /opt/ros/jazzy/setup.bash
mkdir -p -- "$rover_workspace"
cd -- "$rover_workspace"
colcon build --symlink-install \
    --base-paths "$rover_repo/rover_interfaces" "$rover_repo/rover_ros2" \
    --packages-up-to rover_control
echo "Build complete. In each run terminal:"
echo 'source /opt/ros/jazzy/setup.bash'
echo "source $rover_workspace/install/setup.bash"
echo 'export ROS_DOMAIN_ID=2'
echo 'export RMW_IMPLEMENTATION=rmw_fastrtps_cpp'
echo 'export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST'
echo 'Set ROS_STATIC_PEERS to the other computer IPv4 address; see README.md.'
