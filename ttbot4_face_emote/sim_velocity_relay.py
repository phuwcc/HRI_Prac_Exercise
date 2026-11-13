"""Adapt the exercise's /cmd_vel to the simulated Create 3 wheel controller."""
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions


class SimVelocityRelay(Node):
    def __init__(self):
        super().__init__('sim_velocity_relay')
        self.publisher = self.create_publisher(
            Twist, '/diffdrive_controller/cmd_vel_unstamped', 1)
        self.command = Twist()
        self.received_at = float('-inf')
        self.subscription = self.create_subscription(Twist, '/cmd_vel', self.receive, 1)
        self.timer = self.create_timer(0.05, self.tick)

    def receive(self, msg):
        self.command = msg
        self.received_at = time.monotonic()

    def tick(self):
        self.publisher.publish(self.command if time.monotonic() - self.received_at < 0.5
                               else Twist())


def main(args=None):
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = SimVelocityRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.publisher.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
