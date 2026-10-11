"""Runtime health check for the three topics required by the assignment."""

import argparse
import math
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class TopicCheck(Node):
    """Observe sensor topics and verify that cmd_vel has a simulator subscriber."""

    def __init__(self) -> None:
        super().__init__('turtlebot_topic_check')
        self.scan_received = False
        self.odom_received = False
        self.create_subscription(
            LaserScan, 'scan', self._on_scan, qos_profile_sensor_data,
        )
        self.create_subscription(
            Odometry, 'odom', self._on_odom, qos_profile_sensor_data,
        )
        self.cmd_vel_publisher = self.create_publisher(Twist, 'cmd_vel', 10)

    def _on_scan(self, _message: LaserScan) -> None:
        self.scan_received = True

    def _on_odom(self, _message: Odometry) -> None:
        self.odom_received = True

    @property
    def cmd_vel_connected(self) -> bool:
        return self.cmd_vel_publisher.get_subscription_count() > 0

    @property
    def ready(self) -> bool:
        return self.scan_received and self.odom_received and self.cmd_vel_connected


def main() -> None:
    parser = argparse.ArgumentParser(description='Check TurtleBot 4 simulation topics.')
    parser.add_argument('--timeout', type=float, default=30.0)
    args, ros_args = parser.parse_known_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')

    rclpy.init(args=ros_args)
    node = TopicCheck()
    deadline = time.monotonic() + args.timeout

    try:
        while rclpy.ok() and time.monotonic() < deadline and not node.ready:
            rclpy.spin_once(node, timeout_sec=0.1)

        status = {
            '/scan publishes LaserScan': node.scan_received,
            '/odom publishes Odometry': node.odom_received,
            '/cmd_vel has a subscriber': node.cmd_vel_connected,
        }
        for label, passed in status.items():
            print(f'[{"PASS" if passed else "FAIL"}] {label}')

        if not all(status.values()):
            raise SystemExit(1)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()

    print('TurtleBot 4 topic check passed.')
    print('Use teleop and observe odometry to verify actual robot movement.')
