"""Seed AMCL once and only unlock Nav2 after localization is usable."""

import math
import time

from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener


class NavigationReady(Node):
    """Wait for map, scan, AMCL pose, and the transforms navigation needs."""

    def __init__(self):
        super().__init__('navigation_ready')
        self.declare_parameter('auto_initial_pose', True)
        for name in ('initial_x', 'initial_y', 'initial_yaw'):
            self.declare_parameter(name, 0.0)
        self.declare_parameter('timeout', 180.0)

        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.pose = None
        self.scan = None
        self.map_received = False
        self.sent = False
        self.state_future = None
        self.amcl_active = False
        self.state_client = self.create_client(GetState, 'amcl/get_state')
        self.publisher = self.create_publisher(PoseWithCovarianceStamped, 'initialpose', 1)
        self.create_subscription(
            PoseWithCovarianceStamped,
            'amcl_pose',
            self._on_pose,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.create_subscription(LaserScan, 'scan', self._on_scan, qos_profile_sensor_data)
        self.create_subscription(
            OccupancyGrid,
            'map',
            self._on_map,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.get_logger().info(
            'Waiting for AMCL, map, scan, and TF. Nav2 starts after localization is ready.',
        )

    def _on_pose(self, message):
        self.pose = message

    def _on_scan(self, message):
        self.scan = message

    def _on_map(self, _message):
        self.map_received = True

    def poll(self):
        if self.state_future is not None and self.state_future.done():
            result = self.state_future.result()
            self.amcl_active = (
                result is not None
                and result.current_state.id == State.PRIMARY_STATE_ACTIVE
            )
            self.state_future = None
        if not self.amcl_active:
            if self.state_future is None and self.state_client.service_is_ready():
                self.state_future = self.state_client.call_async(GetState.Request())
            return False
        if not self.map_received or self.scan is None or self.get_clock().now().nanoseconds == 0:
            return False
        if not self.buffer.can_transform('odom', 'base_link', rclpy.time.Time()):
            return False

        if (
            self.pose is None
            and not self.sent
            and self.get_parameter('auto_initial_pose').value
        ):
            if self.publisher.get_subscription_count() == 0:
                return False
            message = PoseWithCovarianceStamped()
            message.header.frame_id = 'map'
            message.pose.pose.position.x = self.get_parameter('initial_x').value
            message.pose.pose.position.y = self.get_parameter('initial_y').value
            yaw = self.get_parameter('initial_yaw').value
            message.pose.pose.orientation.z = math.sin(yaw / 2.0)
            message.pose.pose.orientation.w = math.cos(yaw / 2.0)
            message.pose.covariance[0] = message.pose.covariance[7] = 0.25
            message.pose.covariance[35] = 0.0685
            self.publisher.publish(message)
            self.sent = True
            self.get_logger().info('Published the initial pose once in the map frame.')

        if self.pose is None or self.pose.header.frame_id != 'map':
            return False
        stamp = rclpy.time.Time.from_msg(self.scan.header.stamp)
        return (
            self.buffer.can_transform('map', 'base_link', stamp)
            and self.buffer.can_transform('map', self.scan.header.frame_id, stamp)
        )


def main(args=None):
    rclpy.init(args=args)
    node = NavigationReady()
    result = 1
    try:
        deadline = time.monotonic() + node.get_parameter('timeout').value
        next_report = time.monotonic() + 10.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.poll():
                node.get_logger().info(
                    'Localization ready: AMCL pose and scan TF are valid. Starting Nav2.',
                )
                result = 0
                break
            if time.monotonic() >= next_report:
                node.get_logger().info(
                    f'Waiting: amcl_active={node.amcl_active}, map={node.map_received}, '
                    f'scan={node.scan is not None}, pose={node.pose is not None}',
                )
                next_report = time.monotonic() + 10.0
        if result and rclpy.ok():
            node.get_logger().error(
                'Localization timed out. Check map/scan/TF or set the initial pose in RViz.',
            )
    except KeyboardInterrupt:
        result = 130
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    raise SystemExit(result)
