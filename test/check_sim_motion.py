"""Run against headless:=true recognition:=false; tests physics, not vision."""
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from ttbot4_face_emote.controller import Controller, Settings


def main():
    rclpy.init()
    node = rclpy.create_node('check_emotion_sim_motion')
    publisher = node.create_publisher(Twist, '/cmd_vel', 1)
    samples = []
    subscription = node.create_subscription(
        Odometry, '/odom', lambda msg: samples.append(msg), 10)

    def drive(emotion, duration):
        controller = Controller(Settings(stable_samples=1))
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            now = time.monotonic()
            controller.observe(emotion, 0.99, now, now)
            v, w = controller.command(now)
            msg = Twist()
            msg.linear.x, msg.angular.z = v, w
            publisher.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.03)
            time.sleep(0.02)

    try:
        deadline = time.monotonic() + 30
        while not samples and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        assert samples, 'No /odom: simulator/controller not ready'
        expected = {'happy': (1, 1), 'sad': (1, -1), 'neutral': (0, 0),
                    'angry': (-1, 0), 'surprise': (0, 1), 'fear': (1, 0)}
        for emotion, (sv, sw) in expected.items():
            drive('neutral', 0.6)
            samples.clear()
            drive(emotion, 0.7)
            assert samples, 'Odometry stopped'
            velocities = [m.twist.twist.linear.x for m in samples]
            angular = [m.twist.twist.angular.z for m in samples]
            v = max(velocities, key=abs)
            w = max(angular, key=abs)
            assert (sv * v > 0.03 if sv else abs(v) < 0.01), (emotion, v)
            assert (sw * w > 0.15 if sw else abs(w) < 0.03), (emotion, w)
            print(f'PASS {emotion}: odom v={v:.3f} m/s, w={w:.3f} rad/s', flush=True)
        # Drop the publisher's heartbeat; relay must zero the controller input.
        deadline = time.monotonic() + 1.3
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.03)
        last = samples[-1].twist.twist
        assert abs(last.linear.x) < 0.01 and abs(last.angular.z) < 0.03
        print('PASS watchdog: simulator stopped after input timeout', flush=True)
    finally:
        publisher.publish(Twist())
        node.destroy_subscription(subscription)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
