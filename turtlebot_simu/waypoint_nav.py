"""Send a sequence of at least three poses to Nav2."""

import argparse
import math
from pathlib import Path
import time

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
import yaml


class CourseworkNavigator(BasicNavigator):
    """Keep the measured AMCL pose to verify action success independently."""

    def __init__(self):
        self.latest_amcl_pose = None
        super().__init__()

    def _amclPoseCallback(self, message):
        self.latest_amcl_pose = message
        super()._amclPoseCallback(message)


def verify_goal_reached(goal: dict, measured_pose, frame: str, tolerance: float) -> None:
    if measured_pose is None or measured_pose.header.frame_id != frame:
        raise RuntimeError('No AMCL pose in the goal frame to verify arrival.')
    position = measured_pose.pose.pose.position
    orientation = measured_pose.pose.pose.orientation
    values = (position.x, position.y, orientation.x, orientation.y,
              orientation.z, orientation.w)
    if not all(math.isfinite(value) for value in values) or not math.isclose(
        sum(value ** 2 for value in values[2:]), 1.0, abs_tol=0.01,
    ):
        raise RuntimeError('Invalid AMCL pose; cannot verify arrival.')
    distance = math.hypot(position.x - float(goal['x']), position.y - float(goal['y']))
    yaw = math.atan2(
        2 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1 - 2 * (orientation.y ** 2 + orientation.z ** 2),
    )
    error = float(goal.get('yaw', 0.0)) - yaw
    yaw_error = abs(math.atan2(math.sin(error), math.cos(error)))
    if distance > tolerance or yaw_error > 0.35:
        raise RuntimeError(
            f'Nav2 returned success but measured pose is not at the goal '
            f'(distance={distance:.3f} m, yaw error={yaw_error:.3f} rad). Check TF/localization.',
        )


def load_goals(path: Path) -> list[dict]:
    """Load and validate waypoint dictionaries from YAML."""
    with path.open(encoding='utf-8') as stream:
        content = yaml.safe_load(stream) or {}
    if not isinstance(content, dict):
        raise ValueError('The goals file must be a YAML mapping.')
    goals = content.get('goals', [])
    if not isinstance(goals, list) or len(goals) < 3:
        raise ValueError('The goals file must contain at least three goals.')
    for index, goal in enumerate(goals, start=1):
        if not isinstance(goal, dict):
            raise ValueError(f'Goal {index} must be a mapping.')
        missing = {'x', 'y'} - goal.keys()
        if missing:
            raise ValueError(f'Goal {index} is missing: {sorted(missing)}')
        for key in ('x', 'y', 'yaw'):
            value = goal.get(key, 0.0)
            try:
                valid = not isinstance(value, bool) and math.isfinite(float(value))
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f'Goal {index}: {key} must be a finite number.')
    locations = {(float(goal['x']), float(goal['y'])) for goal in goals}
    if len(locations) < 3:
        raise ValueError('The goals file must contain at least three different locations.')
    return goals


def wait_for_navigation(navigator: BasicNavigator, timeout: float) -> OccupancyGrid:
    """Wait for AMCL and Nav2 without publishing a default initial pose."""
    clients = {
        name: navigator.create_client(GetState, f'{name}/get_state')
        for name in ('amcl', 'bt_navigator', 'planner_server', 'controller_server')
    }
    pending = {}
    active = set()
    maps = []
    subscription = navigator.create_subscription(
        OccupancyGrid, 'map', maps.append,
        QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                   durability=DurabilityPolicy.TRANSIENT_LOCAL),
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
            f'Navigation readiness timed out; inactive nodes: {missing}; '
            f'AMCL pose received: {navigator.initial_pose_received}. '
            f'Map received: {bool(maps)}. '
            'Set 2D Pose Estimate in RViz and check map/scan/TF.',
        )
    finally:
        navigator.destroy_subscription(subscription)
        for client in clients.values():
            navigator.destroy_client(client)


def validate_goal_cells(goals: list[dict], grid: OccupancyGrid, clearance: float) -> None:
    """Reject goals in walls, unknown space, or outside the loaded map."""
    info = grid.info
    if info.resolution <= 0 or len(grid.data) != info.width * info.height:
        raise RuntimeError('Invalid occupancy grid received.')
    orientation = info.origin.orientation
    yaw = math.atan2(
        2 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1 - 2 * (orientation.y ** 2 + orientation.z ** 2),
    )
    radius = math.ceil(clearance / info.resolution)
    for index, goal in enumerate(goals, start=1):
        dx = float(goal['x']) - info.origin.position.x
        dy = float(goal['y']) - info.origin.position.y
        col = math.floor((math.cos(yaw) * dx + math.sin(yaw) * dy) / info.resolution)
        row = math.floor((-math.sin(yaw) * dx + math.cos(yaw) * dy) / info.resolution)
        for offset_y in range(-radius, radius + 1):
            for offset_x in range(-radius, radius + 1):
                if math.hypot(offset_x, offset_y) > radius:
                    continue
                x, y = col + offset_x, row + offset_y
                if not (0 <= x < info.width and 0 <= y < info.height):
                    raise RuntimeError(f'Goal {index} is outside the map or too near its edge.')
                value = grid.data[y * info.width + x]
                if value < 0 or value >= 65:
                    raise RuntimeError(
                        f'Goal {index} is in/near occupied or unknown space. '
                        'Replace example waypoints with clear points on your map.',
                    )


def make_pose(navigator: BasicNavigator, goal: dict, frame_id: str) -> PoseStamped:
    pose = PoseStamped()
    pose.header.frame_id = frame_id
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = float(goal['x'])
    pose.pose.position.y = float(goal['y'])
    yaw = float(goal.get('yaw', 0.0))
    pose.pose.orientation.z = math.sin(yaw / 2.0)
    pose.pose.orientation.w = math.cos(yaw / 2.0)
    return pose


def main() -> None:
    default_file = Path(
        get_package_share_directory('turtlebot_simu'), 'config', 'waypoints.yaml',
    )
    parser = argparse.ArgumentParser(description='Execute three or more Nav2 goals.')
    parser.add_argument('--goals-file', type=Path, default=default_file)
    parser.add_argument('--frame', default='map')
    parser.add_argument('--goal-timeout', type=float, default=180.0)
    parser.add_argument('--ready-timeout', type=float, default=120.0)
    parser.add_argument('--clearance', type=float, default=0.25)
    args, ros_args = parser.parse_known_args()
    if any(not math.isfinite(t) or t <= 0 for t in (args.goal_timeout, args.ready_timeout)):
        parser.error('Timeouts must be finite and positive.')
    if not math.isfinite(args.clearance) or args.clearance < 0:
        parser.error('--clearance must be finite and nonnegative.')

    try:
        goals = load_goals(args.goals_file.expanduser())
    except (OSError, ValueError, yaml.YAMLError) as error:
        raise SystemExit(f'Invalid goals file: {error}') from error

    rclpy.init(args=ros_args)
    navigator = CourseworkNavigator()
    navigator.set_parameters([rclpy.parameter.Parameter('use_sim_time', value=True)])
    try:
        navigator.get_logger().info(
            'Waiting for Nav2. Set the initial pose in RViz if AMCL has no pose.',
        )
        grid = wait_for_navigation(navigator, args.ready_timeout)
        if args.frame != grid.header.frame_id:
            raise RuntimeError(f'Goal frame must match map frame: {grid.header.frame_id}')
        validate_goal_cells(goals, grid, args.clearance)

        for index, goal in enumerate(goals, start=1):
            pose = make_pose(navigator, goal, args.frame)
            navigator.get_logger().info(
                f'Sending goal {index}/{len(goals)}: '
                f'x={goal["x"]}, y={goal["y"]}, yaw={goal.get("yaw", 0.0)}',
            )
            if not navigator.goToPose(pose):
                raise RuntimeError(f'Goal {index} was rejected by Nav2.')
            deadline = time.monotonic() + args.goal_timeout
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
                time.sleep(0.2)

            result = navigator.getResult()
            if result != TaskResult.SUCCEEDED:
                labels = {
                    TaskResult.CANCELED: 'canceled',
                    TaskResult.FAILED: 'failed',
                }
                raise RuntimeError(
                    f'Goal {index} {labels.get(result, "returned an unknown result")}.',
                )
            # Give the AMCL callback time to deliver the final pose.
            update_deadline = time.monotonic() + 1.0
            while time.monotonic() < update_deadline:
                rclpy.spin_once(navigator, timeout_sec=0.1)
            verify_goal_reached(goal, navigator.latest_amcl_pose, args.frame, 0.35)
            navigator.get_logger().info(f'Goal {index} succeeded.')
    except KeyboardInterrupt:
        if rclpy.ok() and navigator.goal_handle is not None:
            navigator.cancelTask()
        raise SystemExit(130)
    except RuntimeError as error:
        navigator.get_logger().error(str(error))
        raise SystemExit(1) from error
    finally:
        navigator.destroy_node()
        rclpy.try_shutdown()

    print(f'Completed all {len(goals)} navigation goals successfully.')
