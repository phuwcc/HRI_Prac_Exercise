"""Automatically undock and visit at least three map-frame goals with Nav2."""

import math
from pathlib import Path
import time

from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from irobot_create_msgs.action import Undock
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import rclpy
from rclpy.action import ActionClient
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
import yaml


class CourseworkNavigator(BasicNavigator):
    """Navigator that retains the measured AMCL pose for arrival checks."""

    def __init__(self):
        self.latest_amcl_pose = None
        super().__init__(node_name='waypoint_mission')

    def _amclPoseCallback(self, message):
        self.latest_amcl_pose = message
        super()._amclPoseCallback(message)


def load_goals(path):
    """Load and validate three or more distinct finite waypoint poses."""
    with Path(path).expanduser().open(encoding='utf-8') as stream:
        content = yaml.safe_load(stream) or {}
    if not isinstance(content, dict):
        raise ValueError('The goals file must be a YAML mapping.')
    goals = content.get('goals', [])
    if not isinstance(goals, list) or len(goals) < 3:
        raise ValueError('The goals file must contain at least three goals.')
    for index, goal in enumerate(goals, start=1):
        if not isinstance(goal, dict):
            raise ValueError(f'Goal {index} must be a mapping.')
        if {'x', 'y'} - goal.keys():
            raise ValueError(f'Goal {index} must define x and y.')
        for key in ('x', 'y', 'yaw'):
            value = goal.get(key, 0.0)
            try:
                valid = not isinstance(value, bool) and math.isfinite(float(value))
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f'Goal {index}: {key} must be a finite number.')
    if len({(float(goal['x']), float(goal['y'])) for goal in goals}) < 3:
        raise ValueError('The goals file must contain at least three different locations.')
    return goals


def validate_goal_cells(goals, grid, clearance):
    """Reject waypoints that are unknown, occupied, outside, or too near a wall."""
    info = grid.info
    if info.resolution <= 0 or len(grid.data) != info.width * info.height:
        raise RuntimeError('Received an invalid occupancy grid.')
    orientation = info.origin.orientation
    map_yaw = math.atan2(
        2 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1 - 2 * (orientation.y ** 2 + orientation.z ** 2),
    )
    radius = math.ceil(clearance / info.resolution)
    for index, goal in enumerate(goals, start=1):
        dx = float(goal['x']) - info.origin.position.x
        dy = float(goal['y']) - info.origin.position.y
        col = math.floor((math.cos(map_yaw) * dx + math.sin(map_yaw) * dy) / info.resolution)
        row = math.floor((-math.sin(map_yaw) * dx + math.cos(map_yaw) * dy) / info.resolution)
        for offset_y in range(-radius, radius + 1):
            for offset_x in range(-radius, radius + 1):
                if math.hypot(offset_x, offset_y) > radius:
                    continue
                x_cell, y_cell = col + offset_x, row + offset_y
                if not (0 <= x_cell < info.width and 0 <= y_cell < info.height):
                    raise RuntimeError(f'Goal {index} is outside the map or near its edge.')
                value = grid.data[y_cell * info.width + x_cell]
                if value < 0 or value >= 65:
                    raise RuntimeError(
                        f'Goal {index} is in/near occupied or unknown space. '
                        'Update config/waypoints_small_room.yaml using RViz coordinates.',
                    )


def verify_goal_reached(goal, measured_pose, frame, tolerance):
    if measured_pose is None or measured_pose.header.frame_id != frame:
        raise RuntimeError('No AMCL pose in the goal frame to verify arrival.')
    position = measured_pose.pose.pose.position
    orientation = measured_pose.pose.pose.orientation
    distance = math.hypot(position.x - float(goal['x']), position.y - float(goal['y']))
    yaw = math.atan2(
        2 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1 - 2 * (orientation.y ** 2 + orientation.z ** 2),
    )
    error = float(goal.get('yaw', 0.0)) - yaw
    yaw_error = abs(math.atan2(math.sin(error), math.cos(error)))
    if distance > tolerance or yaw_error > 0.40:
        raise RuntimeError(
            f'Nav2 reported success, but AMCL error is distance={distance:.3f} m, '
            f'yaw={yaw_error:.3f} rad.',
        )


def wait_for_navigation(navigator, timeout):
    """Wait for active Nav2 lifecycle nodes, AMCL, and the saved map."""
    clients = {
        name: navigator.create_client(GetState, f'{name}/get_state')
        for name in ('amcl', 'bt_navigator', 'planner_server', 'controller_server')
    }
    pending = {}
    active = set()
    maps = []
    subscription = navigator.create_subscription(
        OccupancyGrid,
        'map',
        maps.append,
        QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        ),
    )
    deadline = time.monotonic() + timeout
    try:
        while rclpy.ok() and time.monotonic() < deadline:
            for name, client in clients.items():
                if name in active:
                    continue
                future = pending.get(name)
                if future is not None and future.done():
                    response = future.result()
                    if response is not None and response.current_state.label == 'active':
                        active.add(name)
                    pending.pop(name)
                elif future is None and client.service_is_ready():
                    pending[name] = client.call_async(GetState.Request())
            if len(active) == len(clients) and navigator.initial_pose_received and maps:
                return maps[-1]
            rclpy.spin_once(navigator, timeout_sec=0.1)
        missing = sorted(set(clients) - active)
        raise RuntimeError(
            f'Navigation readiness timed out; inactive={missing}, '
            f'AMCL pose={navigator.initial_pose_received}, map={bool(maps)}.',
        )
    finally:
        navigator.destroy_subscription(subscription)
        for client in clients.values():
            navigator.destroy_client(client)


def make_pose(navigator, goal, frame):
    pose = PoseStamped()
    pose.header.frame_id = frame
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = float(goal['x'])
    pose.pose.position.y = float(goal['y'])
    yaw = float(goal.get('yaw', 0.0))
    pose.pose.orientation.z = math.sin(yaw / 2.0)
    pose.pose.orientation.w = math.cos(yaw / 2.0)
    return pose


def auto_undock(navigator, timeout):
    """Undock before navigation and fail clearly if the action is unavailable."""
    client = ActionClient(navigator, Undock, 'undock')
    deadline = time.monotonic() + timeout
    try:
        while rclpy.ok() and time.monotonic() < deadline:
            if client.wait_for_server(timeout_sec=0.5):
                break
        else:
            raise RuntimeError('The /undock action server did not become available.')

        navigator.get_logger().info('Sending automatic undock request.')
        goal_future = client.send_goal_async(Undock.Goal())
        while rclpy.ok() and not goal_future.done() and time.monotonic() < deadline:
            rclpy.spin_once(navigator, timeout_sec=0.1)
        if not goal_future.done() or goal_future.result() is None:
            raise RuntimeError('Undock goal request timed out.')
        handle = goal_future.result()
        if not handle.accepted:
            raise RuntimeError('Undock goal was rejected.')
        result_future = handle.get_result_async()
        while rclpy.ok() and not result_future.done() and time.monotonic() < deadline:
            rclpy.spin_once(navigator, timeout_sec=0.1)
        if not result_future.done():
            handle.cancel_goal_async()
            raise RuntimeError('Undock action timed out.')
        if result_future.result().status != GoalStatus.STATUS_SUCCEEDED:
            raise RuntimeError(f'Undock failed with status {result_future.result().status}.')
        navigator.get_logger().info('Undock succeeded.')
    finally:
        client.destroy()


def main(args=None):
    rclpy.init(args=args)
    navigator = CourseworkNavigator()
    default_goals = str(Path(
        get_package_share_directory('ttbot4_nav_detect'),
        'config',
        'waypoints_small_room.yaml',
    ))
    navigator.declare_parameter('goals_file', default_goals)
    navigator.declare_parameter('frame_id', 'map')
    navigator.declare_parameter('ready_timeout', 240.0)
    navigator.declare_parameter('goal_timeout', 180.0)
    navigator.declare_parameter('goal_tolerance', 0.35)
    navigator.declare_parameter('clearance', 0.25)
    navigator.declare_parameter('auto_undock', True)
    navigator.declare_parameter('undock_timeout', 45.0)

    exit_code = 0
    try:
        goals = load_goals(navigator.get_parameter('goals_file').value)
        frame = str(navigator.get_parameter('frame_id').value)
        navigator.get_logger().info('Waiting for localized, active Nav2.')
        grid = wait_for_navigation(
            navigator, float(navigator.get_parameter('ready_timeout').value),
        )
        if frame != grid.header.frame_id:
            raise RuntimeError(
                f'Goal frame {frame!r} does not match map frame '
                f'{grid.header.frame_id!r}.',
            )
        validate_goal_cells(
            goals, grid, float(navigator.get_parameter('clearance').value),
        )
        if navigator.get_parameter('auto_undock').value:
            auto_undock(
                navigator, float(navigator.get_parameter('undock_timeout').value),
            )

        for index, goal in enumerate(goals, start=1):
            navigator.get_logger().info(
                f'Goal {index}/{len(goals)}: x={goal["x"]}, y={goal["y"]}, '
                f'yaw={goal.get("yaw", 0.0)}',
            )
            if not navigator.goToPose(make_pose(navigator, goal, frame)):
                raise RuntimeError(f'Goal {index} was rejected by Nav2.')
            deadline = time.monotonic() + float(navigator.get_parameter('goal_timeout').value)
            next_feedback = time.monotonic() + 5.0
            while not navigator.isTaskComplete():
                if time.monotonic() >= deadline:
                    navigator.cancelTask()
                    raise RuntimeError(f'Goal {index} timed out.')
                if time.monotonic() >= next_feedback:
                    feedback = navigator.getFeedback()
                    if feedback is not None:
                        navigator.get_logger().info(
                            f'Goal {index}: {feedback.distance_remaining:.2f} m remaining.',
                        )
                    next_feedback = time.monotonic() + 5.0
                time.sleep(0.1)
            if navigator.getResult() != TaskResult.SUCCEEDED:
                raise RuntimeError(f'Goal {index} did not succeed.')
            update_deadline = time.monotonic() + 1.0
            while time.monotonic() < update_deadline:
                rclpy.spin_once(navigator, timeout_sec=0.1)
            verify_goal_reached(
                goal,
                navigator.latest_amcl_pose,
                frame,
                float(navigator.get_parameter('goal_tolerance').value),
            )
            navigator.get_logger().info(f'Goal {index} reached and verified by AMCL.')
        navigator.get_logger().info(f'Mission complete: visited all {len(goals)} goals.')
    except KeyboardInterrupt:
        exit_code = 130
        if navigator.goal_handle is not None:
            navigator.cancelTask()
    except (OSError, ValueError, yaml.YAMLError, RuntimeError) as error:
        exit_code = 1
        navigator.get_logger().error(str(error))
    finally:
        navigator.destroy_node()
        rclpy.try_shutdown()
    raise SystemExit(exit_code)
