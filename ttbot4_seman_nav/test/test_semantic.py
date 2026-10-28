import math
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from ttbot4_seman_nav.commands import CommandParser
from ttbot4_seman_nav.map_data import MapData, load_regions
from ttbot4_seman_nav.segmentation import generate


@pytest.fixture
def regions():
    return [
        {'id': 'A', 'name': 'Phòng học', 'aliases': []},
        {'id': 'B', 'name': 'Phòng thí nghiệm', 'aliases': ['phòng lab']},
        {'id': 'C', 'name': 'Hành lang', 'aliases': ['hành lang C']},
    ]


@pytest.mark.parametrize('text,expected', [
    ('Đi đến khu vực A.', ['A']),
    ('Di chuyển từ khu vực A đến khu vực B.', ['A', 'B']),
    ('Đi đến phòng thí nghiệm.', ['B']),
    ('Đi từ phòng A qua hành lang C rồi đến phòng B', ['A', 'C', 'B']),
    ('di den phong thi nghiem', ['B']),
    ('Dừng lại!', None),
])
def test_commands(regions, text, expected):
    assert CommandParser(regions).parse(text) == expected


@pytest.mark.parametrize('text', ['Đi đến khu vực Z', 'Đi từ Z đến B', 'Đi đến A và Z', 'xin chào'])
def test_unknown_rejected(regions, text):
    with pytest.raises(ValueError):
        CommandParser(regions).parse(text)


def make_map(tmp_path, yaw=0):
    image = np.full((80, 120), 254, np.uint8)
    image[[0,-1], :] = 0
    image[:, [0,-1]] = 0
    image[30:40, 20:30] = 128  # unknown must never become a safe destination
    cv2.imwrite(str(tmp_path/'map.pgm'), image)
    config = {'image': 'map.pgm', 'resolution': .05, 'origin': [-2., -1., yaw],
              'negate': 0, 'free_thresh': .25, 'occupied_thresh': .65}
    path = tmp_path/'map.yaml'
    path.write_text(yaml.safe_dump(config))
    return path


def test_geometry_and_clearance(tmp_path):
    grid = MapData(make_map(tmp_path, yaw=math.pi/3))
    for pixel in [(0,0), (40,60), (119,79)]:
        assert grid.world_to_pixel(*grid.pixel_to_world(*pixel)) == pixel
    assert not grid.safe(*grid.pixel_to_world(25,35), .1)
    assert not grid.safe(*grid.pixel_to_world(1,1), .3)
    assert grid.safe(*grid.pixel_to_world(60,50), .3)
    assert not grid.safe(float('nan'), 0, .3)


def test_manual_segmentation(tmp_path, regions):
    path = make_map(tmp_path)
    for r, (left,right) in zip(regions, [(2,38),(40,77),(79,117)]):
        r['polygon'] = [[left,2],[right,2],[right,77],[left,77]]
    polygons = tmp_path/'polygons.yaml'
    polygons.write_text(yaml.safe_dump({'regions': regions}))
    output = tmp_path/'regions.yaml'
    generate(path, output, polygons=polygons)
    data, grid = load_regions(output)
    assert len(data['regions']) == 3
    assert output.with_suffix('.png').is_file()
    for region in data['regions']:
        assert grid.safe(region['goal']['x'], region['goal']['y'], .3)
    regions[1]['polygon'] = regions[0]['polygon']
    polygons.write_text(yaml.safe_dump({'regions': regions}))
    with pytest.raises(ValueError, match='overlap'):
        generate(path, output, polygons=polygons)


def test_automatic_rooms(tmp_path):
    path = make_map(tmp_path)
    image = cv2.imread(str(tmp_path/'map.pgm'), 0)
    image[:,40] = image[:,80] = 0
    image[37:43,40] = image[37:43,80] = 254
    cv2.imwrite(str(tmp_path/'map.pgm'), image)
    result = generate(path, tmp_path/'auto.yaml', doorway=.8, min_area=.3)
    assert len(result['regions']) == 3


def test_no_invented_rooms(tmp_path):
    with pytest.raises(ValueError, match='room cores'):
        generate(make_map(tmp_path), tmp_path/'auto.yaml', doorway=.8)
