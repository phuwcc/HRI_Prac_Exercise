"""Verify ROS callbacks publish a stop on signal loss without requiring a dock."""

import json
import math
import time
from unittest.mock import Mock

import pytest
import rclpy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String

from ttbot4_handges_control.robot_behavior_node import RobotBehaviorNode


@pytest.fixture
def node():
    rclpy.init()
    instance = RobotBehaviorNode()
    yield instance
    instance.destroy_node()
    rclpy.shutdown()


def ready(node):
    now = time.monotonic()
    node.odom_time = node.scan_time = now
    node.clearance = math.inf
    node.on_tracking(Bool(data=True))


def test_stop_and_missing_scan_publish_zero(node):
    ready(node)
    node.publish_velocity = Mock()
    node.on_gesture(String(data='Victory'))
    node.on_gesture(String(data='Thumb_Up'))
    node.tick()
    assert node.publish_velocity.call_args.args[0] > 0
    node.on_gesture(String(data='Open_Palm'))
    node.publish_velocity.assert_called_with()
    assert node.controller.active is None
    node.on_gesture(String(data='Thumb_Up'))
    node.scan_time = -math.inf
    node.tick()
    node.publish_velocity.assert_called_with(0.0, 0.0)
    assert node.controller.active is None


def test_obstacle_and_invalid_scan_block_motion(node):
    ready(node)
    scan = LaserScan(range_min=.1, range_max=10.0, ranges=[1.0, .25, math.inf])
    node.on_scan(scan)
    node.on_gesture(String(data='Victory'))
    node.on_gesture(String(data='Thumb_Up'))
    assert node.controller.active is None
    assert node.controller.status == 'OBSTACLE_STOP'
    scan.ranges = [math.nan, 0.0, math.inf]
    node.on_scan(scan)
    assert node.clearance == 0


def test_motion_starts_with_scan_and_odometry_without_dock_status(node):
    ready(node)
    node.publish_velocity = Mock()
    node.on_gesture(String(data='Victory'))
    node.on_gesture(String(data='Thumb_Up'))
    node.tick()
    assert node.controller.status == 'RUNNING: circle'
    assert node.publish_velocity.call_args.args[0] > 0
    assert node.publish_velocity.call_args.args[1] > 0


def test_dashboard_feedback_reports_robot_selection_and_sensor_health(node):
    ready(node)
    node.state.publish = Mock()
    node.on_gesture(String(data='Victory'))
    node.tick()
    payload = json.loads(node.state.publish.call_args.args[0].data)
    assert payload['selected'] == 'circle'
    assert payload['status'] == 'SELECTED: circle'
    assert payload['active'] is None
    assert payload['sensors_ready'] is True
    assert payload['clearance'] is None  # Infinity is encoded as valid JSON null.
    assert payload['control_signal'] is True
    node.scan_time = -math.inf
    node.controller.last_frame = -math.inf
    node.tick()
    payload = json.loads(node.state.publish.call_args.args[0].data)
    assert payload['sensors_ready'] is False
    assert payload['control_signal'] is False
    assert payload['selected'] == 'circle'


def test_missing_hand_continues_motion_but_camera_loss_stops(node):
    ready(node)
    node.controller.receive('Victory', time.monotonic())
    node.controller.receive('Thumb_Up', time.monotonic())
    node.publish_velocity = Mock()
    # No stable command labels are coming through; the hand tracker remains alive.
    for _ in range(10):
        node.on_tracking(Bool(data=True))
        node.on_gesture(String(data='None'))
        node.tick()
        assert node.controller.active == 'circle'
    node.controller.last_hand = time.monotonic() - 30
    node.on_tracking(Bool(data=False))
    node.tick()
    assert node.controller.active == 'circle'
    assert node.publish_velocity.call_args.args[0] > 0
    node.controller.last_frame = time.monotonic() - node.controller.settings.signal_timeout - .1
    node.tick()
    assert node.controller.status == 'SIGNAL_LOST'
    node.publish_velocity.assert_called_with(0.0, 0.0)
