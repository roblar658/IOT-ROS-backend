import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'smartguard_ros'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name] if os.path.exists('resource/' + package_name) else []),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'msg'), glob('msg/*.msg')),
        (os.path.join('share', package_name, 'srv'), glob('srv/*.srv')),
        (os.path.join('share', package_name, 'action'), glob('action/*.action')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='SmartGuard ROS Team',
    maintainer_email='dev@smartguard.iot',
    description='ROS 2 Smart Home incident verification, polling, workflows and emergency response.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'gateway_polling_node = smartguard_ros.gateway_polling_node:main',
            'verification_node = smartguard_ros.verification_node:main',
            'workflow_emergency_node = smartguard_ros.workflow_emergency_node:main',
            'device_manager_node = smartguard_ros.device_manager_node:main',
            'predictive_maintenance_node = smartguard_ros.predictive_maintenance_node:main',
            'sensor_nodes = smartguard_ros.sensor_nodes:main',
            'notification_dispatch_node = smartguard_ros.notification_dispatch_node:main',
            'demo_runner = smartguard_ros.demo_runner:main',
        ],
    },
)
