"""
ROS 2 Launch file for SmartGuard Smart Home Architecture.
Launches all sensor nodes, actuator nodes, polling gateway, incident verification engine,
predictive maintenance engine, emergency workflow action server, device manager, and notification dispatcher.
"""

from launch import LaunchDescription
from launch_ros.actions import Node, LifecycleNode

def generate_launch_description():
    return LaunchDescription([
        # 1. Device Manager & Lifecycle Orchestrator
        Node(
            package='smartguard_ros',
            executable='device_manager_node',
            name='device_manager_node',
            output='screen'
        ),

        # 2. Perception & Sensor Nodes
        Node(
            package='smartguard_ros',
            executable='sensor_nodes',
            name='smart_home_sensors',
            output='screen'
        ),

        # 3. Edge Gateway & Polling Engine
        Node(
            package='smartguard_ros',
            executable='gateway_polling_node',
            name='gateway_polling_node',
            output='screen'
        ),

        # 4. Incident Verification Engine (IVE)
        Node(
            package='smartguard_ros',
            executable='verification_node',
            name='incident_verification_node',
            output='screen'
        ),

        # 5. Predictive Maintenance Engine
        Node(
            package='smartguard_ros',
            executable='predictive_maintenance_node',
            name='predictive_maintenance_node',
            output='screen'
        ),

        # 6. Workflow & Emergency Response Action Server
        Node(
            package='smartguard_ros',
            executable='workflow_emergency_node',
            name='workflow_emergency_node',
            output='screen'
        ),

        # 7. Notification & CAP Emergency Dispatch
        Node(
            package='smartguard_ros',
            executable='notification_dispatch_node',
            name='notification_dispatch_node',
            output='screen'
        ),
    ])
