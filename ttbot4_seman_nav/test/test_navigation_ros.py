"""Exercise the real ROS action client with a deterministic fake Nav2 server."""
import math
import time

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionServer
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
import yaml

from ttbot4_seman_nav.navigation import VoiceNavigation
from test_semantic import make_map


@pytest.fixture
def ros_system(tmp_path):
    path = make_map(tmp_path)
    config = {'map': str(path), 'frame_id': 'map', 'clearance': .3, 'regions': [
        {'id': 'A', 'name': 'Phòng học', 'goal': {'x': .5, 'y': .5, 'yaw': 0.}},
        {'id': 'B', 'name': 'Phòng thí nghiệm', 'goal': {'x': 1., 'y': .5, 'yaw': 0.}},
        {'id': 'C', 'name': 'Hành lang', 'goal': {'x': 1.5, 'y': .5, 'yaw': 0.}},
    ]}
    regions = tmp_path/'regions.yaml'
    regions.write_text(yaml.safe_dump(config, allow_unicode=True))
    rclpy.init(args=['--ros-args', '-p', f'regions_file:={regions}'])
    server_node = Node('test_nav2')
    received = []
    behavior = {'abort': False}

    def execute(handle):
        received.append(handle.request.pose.pose.position.x)
        if behavior['abort']:
            handle.abort()
        else:
            handle.succeed()
        return NavigateToPose.Result()

    server = ActionServer(server_node, NavigateToPose, 'navigate_to_pose', execute)
    node = VoiceNavigation()
    msg = OccupancyGrid()
    msg.header.frame_id = 'map'
    msg.info.width, msg.info.height = 120, 80
    msg.info.resolution = .05
    msg.info.origin.position.x, msg.info.origin.position.y = -2., -1.
    msg.info.origin.orientation.w = 1.
    values = np.where(node.grid.free[::-1], 0, -1).astype(np.int8)
    msg.data = values.reshape(-1).tolist()
    node.on_map(msg)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    executor.add_node(server_node)
    assert node.client.wait_for_server(timeout_sec=5.)
    yield node, executor, received, behavior
    executor.shutdown()
    server.destroy()
    node.destroy_node()
    server_node.destroy_node()
    rclpy.shutdown()


def spin_done(node, executor):
    end = time.monotonic()+5
    while node.active and time.monotonic() < end:
        executor.spin_once(timeout_sec=.05)
    assert not node.active


def test_real_action_route_order(ros_system):
    node, executor, received, _ = ros_system
    node.on_command(String(data='Đi từ A qua C rồi đến B'))
    spin_done(node, executor)
    assert received == [.5, 1.5, 1.]


def test_abort_stops_remaining_goals(ros_system):
    node, executor, received, behavior = ros_system
    behavior['abort'] = True
    node.on_command(String(data='Đi từ A đến B'))
    spin_done(node, executor)
    assert received == [.5]
    assert node.route == []


def test_unknown_and_mismatched_map_do_not_send(ros_system):
    node, executor, received, _ = ros_system
    node.on_command(String(data='Đi từ A đến Z'))
    assert not node.active
    node.live_map.info.origin.position.x = 99.
    node.on_command(String(data='Đi đến A'))
    assert not node.active
    assert received == []


def test_cancel_before_acceptance_does_not_advance(ros_system):
    node, executor, received, _ = ros_system
    node.on_command(String(data='Đi từ A đến B'))
    node.on_command(String(data='Dừng lại'))
    spin_done(node, executor)
    assert received == [.5]
    assert node.route == []
