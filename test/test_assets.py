from pathlib import Path
import importlib.util
import math
import shlex
import xml.etree.ElementTree as ET

import pytest
import yaml

from launch import LaunchContext
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription

from turtlebot_simu.save_map import map_prefix
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseWithCovarianceStamped
from turtlebot_simu.waypoint_nav import load_goals, validate_goal_cells, verify_goal_reached
from turtlebot_simu import launch_support


ROOT = Path(__file__).parents[1]


def test_small_room_world_is_local_and_six_meters_wide():
    world = ET.parse(ROOT / 'worlds' / 'small_room.sdf').getroot().find('world')
    assert world.attrib['name'] == 'small_room'
    assert not world.findall('.//include')
    walls = world.find("model[@name='walls']")
    west = walls.find("link[@name='west']")
    east = walls.find("link[@name='east']")
    west_x = float(west.findtext('pose').split()[0])
    east_x = float(east.findtext('pose').split()[0])
    thickness = float(west.findtext('collision/geometry/box/size').split()[0])
    assert east_x - west_x - thickness == pytest.approx(6.0)


@pytest.mark.parametrize('goal', load_goals(ROOT / 'config' / 'waypoints_small_room.yaml'))
def test_small_room_example_goals_clear_geometry(goal):
    world = ET.parse(ROOT / 'worlds' / 'small_room.sdf').getroot().find('world')
    assert -3 < goal['x'] < 3 and -3 < goal['y'] < 3
    for model in world.findall('model'):
        pose = [float(v) for v in model.findtext('pose', '0 0 0 0 0 0').split()]
        for link in model.findall('link'):
            offset = [float(v) for v in link.findtext('pose', '0 0 0 0 0 0').split()]
            dx, dy = goal['x'] - pose[0] - offset[0], goal['y'] - pose[1] - offset[1]
            for geometry in link.findall('collision/geometry'):
                box = geometry.find('box')
                cylinder = geometry.find('cylinder')
                if box is not None:
                    width, height, _ = map(float, box.findtext('size').split())
                    distance = math.hypot(max(abs(dx) - width / 2, 0),
                                          max(abs(dy) - height / 2, 0))
                    assert distance >= 0.35
                elif cylinder is not None:
                    assert math.hypot(dx, dy) - float(cylinder.findtext('radius')) >= 0.35


@pytest.mark.parametrize('headless', ['false', 'true'])
def test_small_room_launch_uses_absolute_sdf_and_logical_world(monkeypatch, headless):
    original = launch_support.get_package_share_directory
    monkeypatch.setattr(launch_support, 'get_package_share_directory',
                        lambda name: str(ROOT) if name == 'turtlebot_simu' else original(name))
    context = LaunchContext()
    context.launch_configurations.update(
        world='small_room', model='lite', headless=headless, gz_args='',
    )
    for action in launch_support.configure_gazebo(context):
        action.execute(context)
    arguments = shlex.split(context.launch_configurations['gz_args'])
    assert arguments[0] == str(ROOT / 'worlds' / 'small_room.sdf')
    assert ('-s' in arguments) == (headless == 'true')
    assert ('--gui-config' in arguments) == (headless == 'false')
    assert context.launch_configurations['world'] == 'small_room'


def test_builtin_world_keeps_upstream_launch():
    context = LaunchContext()
    context.launch_configurations.update(world='maze', headless='false', gz_args='')
    assert launch_support.configure_gazebo(context) == []


def test_explicit_gazebo_arguments_are_preserved():
    context = LaunchContext()
    context.launch_configurations['gz_args'] = '/tmp/custom.sdf -r -s'
    assert launch_support.configure_gazebo(context) == []


@pytest.mark.parametrize('name', ['simulation', 'mapping', 'navigation'])
def test_launch_defaults_to_small_room(name):
    actions = load_launch(name).generate_launch_description().entities
    context = LaunchContext()
    for action in actions:
        if isinstance(action, DeclareLaunchArgument):
            action.execute(context)
    assert context.launch_configurations['world'] == 'small_room'
    assert context.launch_configurations['headless'] == 'false'


def test_map_yaml_references_existing_image():
    with (ROOT / 'maps' / 'map.yaml').open(encoding='utf-8') as stream:
        config = yaml.safe_load(stream)
    assert (ROOT / 'maps' / config['image']).is_file()
    assert config['resolution'] > 0.0


def test_default_waypoint_file_has_three_goals():
    goals = load_goals(ROOT / 'config' / 'waypoints.yaml')
    assert len(goals) >= 3


def test_map_prefix_strips_known_extensions(tmp_path):
    expected = (tmp_path / 'map').resolve()
    assert map_prefix(str(tmp_path / 'map.yaml')) == expected
    assert map_prefix(str(tmp_path / 'map.pgm')) == expected


@pytest.mark.parametrize('content', [
    '[]', 'goals: text', 'goals: [null, {}, {}]',
    'goals: [{x: .nan, y: 0}, {x: 1, y: 1}, {x: 2, y: 2}]',
    'goals: [{x: 0, y: nope}, {x: 1, y: 1}, {x: 2, y: 2}]',
])
def test_invalid_goals_report_value_error(tmp_path, content):
    path = tmp_path / 'goals.yaml'
    path.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError):
        load_goals(path)


def test_three_goals_must_have_different_locations(tmp_path):
    path = tmp_path / 'goals.yaml'
    path.write_text('goals: [{x: 0, y: 0}, {x: 0, y: 0, yaw: 1}, {x: 1, y: 0}]')
    with pytest.raises(ValueError, match='different locations'):
        load_goals(path)


def load_launch(name):
    path = ROOT / 'launch' / f'{name}.launch.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('name', ['simulation', 'mapping', 'navigation'])
def test_direct_launch_includes_exist(name):
    context = LaunchContext()
    actions = list(load_launch(name).generate_launch_description().entities)
    while actions:
        action = actions.pop(0)
        if isinstance(action, DeclareLaunchArgument):
            action.execute(context)
        elif isinstance(action, GroupAction):
            actions.extend(action.get_sub_entities())
        elif isinstance(action, IncludeLaunchDescription):
            action.launch_description_source.get_launch_description(context)


def test_navigation_rejects_starter_map(tmp_path):
    (tmp_path / 'map.pgm').write_bytes(b'P2\n# STARTER MAP ONLY\n1 1\n255\n254\n')
    (tmp_path / 'map.yaml').write_text('image: map.pgm\n', encoding='utf-8')
    context = LaunchContext()
    context.launch_configurations['map'] = str(tmp_path / 'map.yaml')
    with pytest.raises(RuntimeError, match='starter map'):
        load_launch('navigation').validate_map(context)


def test_navigation_accepts_saved_map(tmp_path):
    (tmp_path / 'map.pgm').write_bytes(b'P5\n1 1\n255\n\xfe')
    (tmp_path / 'map.yaml').write_text(
        'image: map.pgm\nresolution: 0.05\norigin: [0, 0, 0]\n'
        'negate: 0\nfree_thresh: 0.25\noccupied_thresh: 0.65\n', encoding='utf-8',
    )
    context = LaunchContext()
    context.launch_configurations['map'] = str(tmp_path / 'map.yaml')
    assert load_launch('navigation').validate_map(context) == []


def test_navigation_rejects_missing_map_metadata(tmp_path):
    (tmp_path / 'map.pgm').write_bytes(b'P5\n1 1\n255\n\xfe')
    (tmp_path / 'map.yaml').write_text('image: map.pgm\n', encoding='utf-8')
    context = LaunchContext()
    context.launch_configurations['map'] = str(tmp_path / 'map.yaml')
    with pytest.raises(RuntimeError, match='resolution'):
        load_launch('navigation').validate_map(context)


@pytest.mark.parametrize('cell', [-1, 100])
def test_goal_in_unknown_or_occupied_space_is_rejected(cell):
    grid = OccupancyGrid()
    grid.info.resolution = 1.0
    grid.info.width = grid.info.height = 3
    grid.data = [0] * 9
    grid.data[4] = cell
    with pytest.raises(RuntimeError, match='occupied or unknown'):
        validate_goal_cells([{'x': 1.5, 'y': 1.5}], grid, 0.0)


def test_goal_clearance_and_map_boundary():
    grid = OccupancyGrid()
    grid.info.resolution = 1.0
    grid.info.width = grid.info.height = 5
    grid.data = [0] * 25
    grid.data[13] = 100
    validate_goal_cells([{'x': 2.5, 'y': 2.5}], grid, 0.0)
    with pytest.raises(RuntimeError, match='occupied or unknown'):
        validate_goal_cells([{'x': 2.5, 'y': 2.5}], grid, 1.0)
    with pytest.raises(RuntimeError, match='outside the map'):
        validate_goal_cells([{'x': -0.1, 'y': 2.5}], grid, 0.0)


def test_nav2_maps_use_correct_sources():
    config = yaml.safe_load((ROOT / 'config' / 'nav2.yaml').read_text())
    local = config['local_costmap']['local_costmap']['ros__parameters']
    global_map = config['global_costmap']['global_costmap']['ros__parameters']
    assert 'static_layer' not in local['plugins']
    assert 'static_layer' in global_map['plugins']
    assert local['voxel_layer']['scan']['data_type'] == 'LaserScan'
    assert local['use_sim_time'] and global_map['use_sim_time']


def test_action_success_does_not_prove_arrival():
    pose = PoseWithCovarianceStamped()
    pose.header.frame_id = 'map'
    pose.pose.pose.orientation.w = 1.0
    with pytest.raises(RuntimeError, match='not at the goal'):
        verify_goal_reached({'x': 2.0, 'y': 0.0}, pose, 'map', 0.35)


def test_measured_pose_confirms_arrival():
    pose = PoseWithCovarianceStamped()
    pose.header.frame_id = 'map'
    pose.pose.pose.position.x = 2.1
    pose.pose.pose.orientation.w = 1.0
    verify_goal_reached({'x': 2.0, 'y': 0.0}, pose, 'map', 0.35)


def test_invalid_amcl_pose_cannot_confirm_arrival():
    pose = PoseWithCovarianceStamped()
    pose.header.frame_id = 'map'
    pose.pose.pose.position.x = float('nan')
    pose.pose.pose.orientation.w = 1.0
    with pytest.raises(RuntimeError, match='Invalid AMCL pose'):
        verify_goal_reached({'x': 2.0, 'y': 0.0}, pose, 'map', 0.35)
