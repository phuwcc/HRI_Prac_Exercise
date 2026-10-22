"""Translate gesture events into nonblocking, interruptible robot motions."""

import json
import math
import signal
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.signals import SignalHandlerOptions
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String

from .control import Controller, Settings


class RobotBehaviorNode(Node):
    def __init__(self):
        super().__init__('robot_behavior_node')
        defaults = vars(Settings()) | {
            'sensor_timeout': 1.0, 'stop_distance': 0.4,
        }
        for key, value in defaults.items():
            self.declare_parameter(key, value)
        def p(key):
            return float(self.get_parameter(key).value)

        self.controller = Controller(Settings(**{key: p(key) for key in vars(Settings())}))
        self.sensor_timeout = p('sensor_timeout')
        self.stop_distance = p('stop_distance')
        if not all(math.isfinite(v) and v > 0
                   for v in (self.sensor_timeout, self.stop_distance)):
            raise ValueError('Sensor and distance limits must be finite and positive')
        self.pose = (0.0, 0.0, 0.0)
        self.odom_time = self.scan_time = -math.inf
        self.clearance = 0.0
        self.last_status = None
        self.velocity = self.create_publisher(Twist, '/cmd_vel', 1)
        self.status = self.create_publisher(String, '/gesture_control/status', 1)
        self.state = self.create_publisher(String, '/gesture_control/state', 1)
        self.create_subscription(String, '/detected_gesture', self.on_gesture, 1)
        self.create_subscription(
            Bool, '/gesture_control/hand_present', self.on_tracking, 1)
        self.create_subscription(Odometry, '/odom', self.on_odom, qos_profile_sensor_data)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        # Wall clock deliberately remains independent of Gazebo pause / clock jumps.
        self.create_timer(0.05, self.tick)
        self.get_logger().info('Behavior ready; waiting for sensors and confirmed selection.')

    def on_odom(self, message):
        position = message.pose.pose.position
        q = message.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y),
                         1 - 2 * (q.y * q.y + q.z * q.z))
        if all(math.isfinite(v) for v in (position.x, position.y, yaw)):
            self.pose = (position.x, position.y, yaw)
            self.odom_time = time.monotonic()

    def on_scan(self, message):
        # Positive infinity means no return within the scanner's range.
        valid = [v for v in message.ranges if v == math.inf or (
            math.isfinite(v) and message.range_min <= v <= message.range_max)]
        # Treat missing/invalid coverage conservatively, including zero readings.
        coverage = len(valid) / max(1, len(message.ranges))
        self.clearance = min(valid) if valid and coverage >= 0.9 else 0.0
        self.scan_time = time.monotonic()

    def sensors_fresh(self, now):
        return all(now - stamp <= self.sensor_timeout
                   for stamp in (self.odom_time, self.scan_time))

    def on_tracking(self, message):
        self.controller.track(message.data, time.monotonic())

    def on_gesture(self, message):
        now = time.monotonic()
        was_active = self.controller.active
        self.controller.receive(message.data, now)
        if not self.controller.active:
            self.publish_velocity()
        elif not was_active:
            if not self.sensors_fresh(now):
                self.controller.stop('SENSORS_NOT_READY')
            elif self.clearance <= self.stop_distance:
                self.controller.stop('OBSTACLE_STOP')

    def publish_velocity(self, linear=0.0, angular=0.0):
        message = Twist()
        message.linear.x, message.angular.z = float(linear), float(angular)
        self.velocity.publish(message)

    def tick(self):
        now = time.monotonic()
        safe = self.sensors_fresh(now) and self.clearance > self.stop_distance
        linear, angular = self.controller.command(now, self.pose, safe=safe)
        self.publish_velocity(linear, angular)
        text = self.controller.status
        self.status.publish(String(data=text))
        self.state.publish(String(data=json.dumps({
            'status': text,
            'selected': self.controller.selected,
            'active': self.controller.active,
            'sensors_ready': self.sensors_fresh(now),
            'clearance': self.clearance if math.isfinite(self.clearance) else None,
            'obstacle': self.clearance <= self.stop_distance,
            'control_signal': self.controller.signal_status(now) is None,
            'tracking_alive': now - self.controller.last_frame
            <= self.controller.settings.signal_timeout,
            'hand_present': self.controller.hand_present,
            'hand_age': (now - self.controller.last_hand
                         if math.isfinite(self.controller.last_hand) else None),
        }, allow_nan=False)))
        if text != self.last_status:
            self.get_logger().info(text)
            self.last_status = text


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = None
    try:
        node = RobotBehaviorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if node is not None:
            if rclpy.ok():
                node.controller.stop('SHUTDOWN')
                node.publish_velocity()
            node.destroy_node()
        rclpy.try_shutdown()
