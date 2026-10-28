"""Map geometry and goal validation, independent of ROS."""
import math
from pathlib import Path

import cv2
import numpy as np
import yaml


class MapData:
    def __init__(self, filename):
        self.path = Path(filename).expanduser().resolve()
        self.config = yaml.safe_load(self.path.read_text(encoding='utf-8'))
        c = self.config
        if c.get('mode', 'trinary') != 'trinary':
            raise ValueError('Only trinary occupancy maps are supported.')
        self.resolution = float(c['resolution'])
        self.origin = tuple(float(v) for v in c['origin'])
        if (not math.isfinite(self.resolution) or self.resolution <= 0
                or len(self.origin) != 3 or not all(map(math.isfinite, self.origin))):
            raise ValueError('Invalid resolution/origin.')
        if not 0 <= c['free_thresh'] < c['occupied_thresh'] <= 1 or c['negate'] not in (0, 1):
            raise ValueError('Invalid occupancy thresholds/negate.')
        self.image = cv2.imread(str(self.path.parent / c['image']), cv2.IMREAD_GRAYSCALE)
        if self.image is None:
            raise ValueError('Cannot read map image.')
        occupancy = self.image.astype(float) / 255.0
        if not c['negate']:
            occupancy = 1.0 - occupancy
        self.free = (occupancy < float(c['free_thresh'])).astype(np.uint8)
        # Padding treats outside the image as occupied, including all-white maps.
        self.clearance = cv2.distanceTransform(
            np.pad(self.free, 1), cv2.DIST_L2, cv2.DIST_MASK_PRECISE
        )[1:-1, 1:-1] * self.resolution

    def pixel_to_world(self, u, v):
        x = (u + 0.5) * self.resolution
        y = (self.image.shape[0] - v - 0.5) * self.resolution
        ox, oy, yaw = self.origin
        return (ox + math.cos(yaw)*x - math.sin(yaw)*y,
                oy + math.sin(yaw)*x + math.cos(yaw)*y)

    def world_to_pixel(self, x, y):
        ox, oy, yaw = self.origin
        dx, dy = x-ox, y-oy
        u = math.floor((math.cos(yaw)*dx + math.sin(yaw)*dy) / self.resolution)
        row = math.floor((-math.sin(yaw)*dx + math.cos(yaw)*dy) / self.resolution)
        return u, self.image.shape[0] - 1 - row

    def safe(self, x, y, clearance):
        if not all(map(math.isfinite, [x, y, clearance])) or clearance <= 0:
            return False
        u, v = self.world_to_pixel(x, y)
        h, w = self.image.shape
        return 0 <= u < w and 0 <= v < h and bool(self.free[v, u]) and self.clearance[v, u] >= clearance


def load_regions(filename):
    path = Path(filename).expanduser().resolve()
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if data.get('frame_id') != 'map':
        raise ValueError('Regions must use frame_id: map.')
    map_path = Path(data['map'])
    grid = MapData(map_path if map_path.is_absolute() else path.parent / map_path)
    regions = data['regions']
    if len(regions) < 3:
        raise ValueError('At least three regions are required.')
    ids = set()
    clearance = float(data.get('clearance', 0.3))
    data['clearance'] = clearance
    for r in regions:
        if not isinstance(r['id'], str) or r['id'] in ids or not r['id'].strip():
            raise ValueError('Region IDs must be unique nonempty strings.')
        ids.add(r['id'])
        g = r['goal']
        if not math.isfinite(float(g.get('yaw', 0))) or not grid.safe(float(g['x']), float(g['y']), clearance):
            raise ValueError(f"Unsafe goal for region {r['id']}")
    return data, grid
