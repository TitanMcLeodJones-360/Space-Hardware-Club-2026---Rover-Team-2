from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    xbox = LaunchConfiguration('xbox')
    source = LaunchConfiguration('xbox_source')
    return LaunchDescription([
        DeclareLaunchArgument('xbox', default_value='false'),
        DeclareLaunchArgument('xbox_source', default_value='ros'),
        DeclareLaunchArgument('xbox_port', default_value='15002'),
        DeclareLaunchArgument('controller_id', default_value='0'),
        Node(package='joy', executable='game_controller_node', name='rover_xbox',
             condition=IfCondition(PythonExpression(["'", xbox, "'.lower() == 'true' and '", source, "' == 'ros'"])),
             remappings=[('joy', '/arm/xbox/joy')],
             parameters=[{'device_id': ParameterValue(LaunchConfiguration('controller_id'), value_type=int),
                          'deadzone': 0.0, 'autorepeat_rate': 20.0, 'sticky_buttons': False}]),
        Node(package='rover_control', executable='ground_station', output='screen',
             parameters=[{'use_xbox': ParameterValue(xbox, value_type=bool),
                          'xbox_source': source,
                          'xbox_port': ParameterValue(LaunchConfiguration('xbox_port'), value_type=int)}]),
    ])
