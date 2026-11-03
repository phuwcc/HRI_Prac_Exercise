"""Add the simulator's low dock to a temporary occupancy map for Nav2."""
import math
from pathlib import Path

import cv2
import numpy as np
import yaml

from .map_data import MapData


def write_navigation_map(grid, directory, initial_x, initial_y, initial_yaw):
    pose = (initial_x, initial_y, initial_yaw)
    if not all(math.isfinite(value) for value in pose):
        raise ValueError('Initial pose must be finite to locate the dock in map frame.')
    image_path = grid.path.parent / grid.config['image']
    if ('STARTER MAP ONLY' in grid.path.read_text(encoding='utf-8')
            or b'STARTER MAP ONLY' in image_path.read_bytes()[:256]):
        raise ValueError('Save a real SLAM map before starting navigation.')
    # Upstream turtlebot4_spawn places the dock at +0.157 m, facing back.
    # Its collision box is centered a further +0.045 m, size 0.04 x 0.13 m.
    # Include 0.05 m padding for the grid and small localization errors.
    vertices = []
    c, s = math.cos(initial_yaw), math.sin(initial_yaw)
    for x, y in ((.132, -.115), (.272, -.115), (.272, .115), (.132, .115)):
        vertices.append(grid.world_to_pixel(initial_x+c*x-s*y, initial_y+s*x+c*y))
    image = grid.image.copy()
    cv2.fillPoly(image, [np.asarray(vertices, dtype=np.int32)],
                 255 if grid.config['negate'] else 0)
    directory = Path(directory)
    image_file = directory / 'navigation.pgm'
    if not cv2.imwrite(str(image_file), image):
        raise OSError(f'Cannot write navigation map: {image_file}')
    config = dict(grid.config, image=image_file.name)
    output = directory / 'navigation.yaml'
    output.write_text(yaml.safe_dump(config, sort_keys=False), encoding='utf-8')
    return MapData(output)
