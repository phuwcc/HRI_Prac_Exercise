"""Initialize AMCL once, then gate Nav2 startup on measured pose and TF."""

import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import LaserScan
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from tf2_ros import Buffer, TransformListener


class NavigationReady(Node):
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
            PoseWithCovarianceStamped, 'amcl_pose', self.on_pose,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.create_subscription(LaserScan, 'scan', self.on_scan, qos_profile_sensor_data)
        self.create_subscription(
            OccupancyGrid, 'map', self.on_map,
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL),
        )
        self.get_logger().info(
            'Waiting for AMCL, map, scan and odom TF. Nav2 starts after localization is ready. '
            'In manual mode, set 2D Pose Estimate in RViz now.'
        )

    def on_pose(self, message):
        self.pose = message

    def on_scan(self, message):
        self.scan = message

    def on_map(self, _message):
        self.map_received = True

    def poll(self):
        if self.state_future is not None and self.state_future.done():
            result = self.state_future.result()
            self.amcl_active = result is not None and result.current_state.id == State.PRIMARY_STATE_ACTIVE
            self.state_future = None
        if not self.amcl_active:
            if self.state_future is None and self.state_client.service_is_ready():
                self.state_future = self.state_client.call_async(GetState.Request())
            return False
        if not self.map_received or self.scan is None or self.get_clock().now().nanoseconds == 0:
            return False
        if not self.buffer.can_transform('odom', 'base_link', rclpy.time.Time()):
            return False
        if (self.pose is None and not self.sent
                and self.get_parameter('auto_initial_pose').value):
            if self.publisher.get_subscription_count() == 0:
                return False
            message = PoseWithCovarianceStamped()
            message.header.frame_id = 'map'
            # Zero stamp uses the latest transform and avoids startup extrapolation.
            message.pose.pose.position.x = self.get_parameter('initial_x').value
            message.pose.pose.position.y = self.get_parameter('initial_y').value
            yaw = self.get_parameter('initial_yaw').value
            message.pose.pose.orientation.z = math.sin(yaw / 2)
            message.pose.pose.orientation.w = math.cos(yaw / 2)
            message.pose.covariance[0] = message.pose.covariance[7] = 0.25
            message.pose.covariance[35] = 0.0685
            self.publisher.publish(message)
            self.sent = True
            self.get_logger().info('Published initial pose once in map frame.')
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
                node.get_logger().info('Localization ready: AMCL pose and scan TF valid. Starting Nav2.')
                result = 0
                break
            if time.monotonic() >= next_report:
                node.get_logger().info(
                    f'Waiting: amcl_active={node.amcl_active}, map={node.map_received}, '
                    f'scan={node.scan is not None}, pose={node.pose is not None}, '
                    f'odom_tf={node.buffer.can_transform("odom", "base_link", rclpy.time.Time())}'
                )
                next_report = time.monotonic() + 10.0
        if result and rclpy.ok():
            node.get_logger().error(
                'Localization timeout. Set 2D Pose Estimate or correct initial_x/initial_y/initial_yaw; '
                'also check map, scan and odom. Nav2 was not started.'
            )
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(result)
