"""Ensure startup cannot unlock Nav2 from odometry alone or invalid scan TF."""

from types import SimpleNamespace
from unittest.mock import Mock

from geometry_msgs.msg import PoseWithCovarianceStamped
from sensor_msgs.msg import LaserScan
from turtlebot_simu.navigation_ready import NavigationReady


def ready_state(pose=None):
    scan = LaserScan()
    scan.header.frame_id = 'laser'
    return SimpleNamespace(
        state_future=None, amcl_active=True, map_received=True, scan=scan,
        pose=pose, sent=False, buffer=Mock(), publisher=Mock(),
        get_clock=lambda: SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=1)),
        get_parameter=lambda name: SimpleNamespace(value=False),
    )


def test_odom_alone_does_not_unlock_nav2():
    node = ready_state()
    node.buffer.can_transform.return_value = True
    assert not NavigationReady.poll(node)
    node.publisher.publish.assert_not_called()


def test_missing_scan_transform_does_not_unlock_nav2():
    pose = PoseWithCovarianceStamped()
    pose.header.frame_id = 'map'
    node = ready_state(pose)
    node.buffer.can_transform.side_effect = [True, True, False]
    assert not NavigationReady.poll(node)


def test_valid_pose_and_scan_tf_unlock_nav2():
    pose = PoseWithCovarianceStamped()
    pose.header.frame_id = 'map'
    node = ready_state(pose)
    node.buffer.can_transform.return_value = True
    assert NavigationReady.poll(node)


def test_auto_seed_is_only_sent_once():
    node = ready_state()
    node.get_parameter = lambda name: SimpleNamespace(
        value=True if name == 'auto_initial_pose' else 0.0,
    )
    node.get_logger = lambda: Mock()
    node.buffer.can_transform.return_value = True
    assert not NavigationReady.poll(node)
    assert not NavigationReady.poll(node)
    node.publisher.publish.assert_called_once()
    message = node.publisher.publish.call_args.args[0]
    assert message.header.frame_id == 'map'
    assert message.header.stamp.sec == 0
    assert message.pose.pose.orientation.w == 1.0


def test_seed_waits_for_amcl_subscriber():
    node = ready_state()
    node.get_parameter = lambda name: SimpleNamespace(
        value=True if name == 'auto_initial_pose' else 0.0,
    )
    node.buffer.can_transform.return_value = True
    node.publisher.get_subscription_count.return_value = 0
    assert not NavigationReady.poll(node)
    assert not node.sent
    node.publisher.publish.assert_not_called()
