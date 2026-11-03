"""Exercise the real ROS action client with a deterministic fake Nav2 server."""
import math
import time

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionServer, CancelResponse
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.task import Future
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String
import yaml

from ttbot4_seman_nav.navigation import VoiceNavigation
from test_semantic import make_map


@pytest.fixture
def ros_system(tmp_path, request):
    path = make_map(tmp_path)
    config = {'map': str(path), 'frame_id': 'map', 'clearance': .3, 'regions': [
        {'id': 'A', 'name': 'Phòng học', 'goal': {'x': .5, 'y': .5, 'yaw': 0.}},
        {'id': 'B', 'name': 'Phòng thí nghiệm', 'goal': {'x': 1., 'y': .5, 'yaw': 0.}},
        {'id': 'C', 'name': 'Hành lang', 'goal': {'x': 1.5, 'y': .5, 'yaw': 0.}},
    ]}
    regions = tmp_path/'regions.yaml'
    regions.write_text(yaml.safe_dump(config, allow_unicode=True))
    args = ['--ros-args', '-p', f'regions_file:={regions}']
    for key, value in getattr(request, 'param', {}).items():
        args += ['-p', f'{key}:={str(value).lower()}']
    rclpy.init(args=args)
    server_node = Node('test_nav2')
    received = []
    behavior = {'abort': False, 'hold': False, 'release': Future(), 'cancels': 0}

    async def execute(handle):
        received.append(handle.request.pose.pose.position.x)
        if behavior['hold']:
            await behavior['release']
        if handle.is_cancel_requested:
            handle.canceled()
        elif behavior['abort']:
            handle.abort()
        else:
            handle.succeed()
        return NavigateToPose.Result()

    def cancel(_handle):
        behavior['cancels'] += 1
        return CancelResponse.ACCEPT

    server = ActionServer(server_node, NavigateToPose, 'navigate_to_pose', execute,
                          cancel_callback=cancel)
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


@pytest.mark.parametrize('ros_system', [
    {'use_sim_time': True, 'goal_timeout': .1},
], indirect=True)
@pytest.mark.parametrize('paused_clock', [False, True])
def test_timeout_cancels_goal_without_advancing_sim_time(ros_system, paused_clock):
    node, executor, received, behavior = ros_system
    behavior['hold'] = True
    if paused_clock:
        publisher = node.create_publisher(Clock, '/clock', 10)
        message = Clock()
        message.clock.sec = 10
        end = time.monotonic()+2
        while node.get_clock().now().nanoseconds == 0 and time.monotonic() < end:
            publisher.publish(message)
            executor.spin_once(timeout_sec=.05)
        assert node.get_clock().now().nanoseconds == 10_000_000_000
    node.on_command(String(data='Đi từ A đến B'))
    end = time.monotonic()+3
    while behavior['cancels'] == 0 and time.monotonic() < end:
        executor.spin_once(timeout_sec=.05)
    try:
        assert received == [.5]
        assert behavior['cancels'] == 1
        assert node.cancel_requested
        assert node.route == []
    finally:
        behavior['release'].set_result(None)
        spin_done(node, executor)
    assert received == [.5]
