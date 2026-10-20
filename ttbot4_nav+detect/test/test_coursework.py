from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
import yaml

from ttbot4_nav_detect.object_detector import detections_from_result
from ttbot4_nav_detect.waypoint_mission import load_goals


ROOT = Path(__file__).parents[1]


def test_package_name_is_valid():
    root = ET.parse(ROOT / 'package.xml').getroot()
    assert root.findtext('name') == 'ttbot4_nav_detect'


def test_map_image_exists():
    config = yaml.safe_load((ROOT / 'maps' / 'small_room.yaml').read_text())
    assert (ROOT / 'maps' / config['image']).is_file()
    assert config['resolution'] > 0


def test_world_has_no_external_assets():
    world = ET.parse(ROOT / 'worlds' / 'small_room.sdf').getroot().find('world')
    assert world.attrib['name'] == 'small_room'
    assert not world.findall('.//include')


def test_mission_has_three_distinct_goals():
    goals = load_goals(ROOT / 'config' / 'waypoints_small_room.yaml')
    assert len(goals) >= 3
    assert len({(goal['x'], goal['y']) for goal in goals}) >= 3


@pytest.mark.parametrize('goal', load_goals(ROOT / 'config' / 'waypoints_small_room.yaml'))
def test_goals_are_inside_room(goal):
    assert -3.0 < goal['x'] < 3.0
    assert -3.0 < goal['y'] < 3.0


def test_yolo_result_is_converted_to_metadata():
    class Scalar:
        def __init__(self, value):
            self.value = value

        def item(self):
            return self.value

    class Coordinates:
        def tolist(self):
            return [10.04, 20.06, 30.08, 40.02]

    box = type('Box', (), {
        'cls': [Scalar(0)],
        'conf': [Scalar(0.8764)],
        'xyxy': [Coordinates()],
    })()
    result = type('Result', (), {'boxes': [box], 'names': {0: 'person'}})()
    assert detections_from_result(result) == [{
        'class_id': 0,
        'label': 'person',
        'confidence': 0.876,
        'bbox_xyxy': [10.0, 20.1, 30.1, 40.0],
    }]
