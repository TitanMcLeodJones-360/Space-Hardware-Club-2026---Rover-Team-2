from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("dry_run", default_value="true"),
        DeclareLaunchArgument("serial_port", default_value=""),
        Node(package="rover_control", executable="arm_bridge", output="screen",
             parameters=[{
                 "dry_run": ParameterValue(LaunchConfiguration("dry_run"), value_type=bool),
                 "serial_port": LaunchConfiguration("serial_port"),
             }]),
    ])
