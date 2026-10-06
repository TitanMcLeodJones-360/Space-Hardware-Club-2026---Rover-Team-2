from glob import glob
from setuptools import setup

setup(
    name="rover_control",
    version="0.3.0",
    packages=["rover_control"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/rover_control"]),
        ("share/rover_control", ["package.xml"]),
        ("share/rover_control/launch", glob("launch/*.launch.py")),
        ("share/rover_control/pico/rover_pico", glob("pico/rover_pico/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Rover Software Team",
    maintainer_email="rover@example.invalid",
    description="Ground station, ROS 2 arm bridge, and Pico starter firmware",
    license="Proprietary",
    entry_points={"console_scripts": [
        "ground_station = rover_control.ground_station:main",
        "arm_bridge = rover_control.arm_bridge:main",
    ]},
)
