import math

import pytest

from ttbot4_seman_nav.map_data import MapData
from ttbot4_seman_nav.navigation_map import write_navigation_map
from test_semantic import make_map


@pytest.mark.parametrize('yaw', [0., math.pi/3])
def test_dock_is_occupied_without_changing_original_map(tmp_path, yaw):
    grid = MapData(make_map(tmp_path, yaw=yaw))
    x, y = grid.pixel_to_world(60, 50)
    center = (x+.202*math.cos(yaw), y+.202*math.sin(yaw))
    u, v = grid.world_to_pixel(*center)
    original = (tmp_path/'map.pgm').read_bytes()
    output = tmp_path/'navigation'
    output.mkdir()
    result = write_navigation_map(grid, output, x, y, yaw)
    assert grid.free[v, u]
    assert not result.free[v, u]
    assert not result.safe(*center, .3)
    assert result.resolution == grid.resolution
    assert result.origin == grid.origin
    assert result.image.shape == grid.image.shape
    assert (tmp_path/'map.pgm').read_bytes() == original
    assert result.free[65, 95] == grid.free[65, 95]


def test_starter_map_cannot_bypass_launch_validation(tmp_path):
    path = make_map(tmp_path)
    with path.open('a') as stream:
        stream.write('\n# STARTER MAP ONLY\n')
    with pytest.raises(ValueError, match='real SLAM map'):
        write_navigation_map(MapData(path), tmp_path, 0., 0., 0.)
