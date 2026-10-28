"""Offline occupancy segmentation with automatic room seeds or manual polygons."""
import argparse
import heapq
import os
from pathlib import Path

import cv2
import numpy as np
import yaml

from .map_data import MapData


def automatic_labels(grid, doorway, min_area):
    # Remove narrow door connections, then grow room cores through known free cells.
    cores = (grid.clearance >= doorway / 2).astype(np.uint8)
    count, components, stats, _ = cv2.connectedComponentsWithStats(cores, 8)
    labels = np.zeros_like(components)
    region_id = 0
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] * grid.resolution**2 >= min_area:
            region_id += 1
            labels[components == i] = region_id
    if region_id < 3:
        raise ValueError(
            f'Only {region_id} room cores found. Adjust --doorway-width/--min-area '
            'or use --polygons to mark at least 3 functional areas manually.'
        )
    # Multi-source geodesic growth; never crosses obstacles or unknown pixels.
    queue = []
    h, w = labels.shape
    for v, u in np.argwhere(labels > 0):
        if any(0 <= v+dv < h and 0 <= u+du < w and labels[v+dv, u+du] == 0
               and grid.free[v+dv, u+du] for dv, du in ((1,0),(-1,0),(0,1),(0,-1))):
            heapq.heappush(queue, (0, int(v), int(u), int(labels[v,u])))
    while queue:
        distance, v, u, label = heapq.heappop(queue)
        for dv, du in ((1,0),(-1,0),(0,1),(0,-1)):
            nv, nu = v+dv, u+du
            if 0 <= nv < h and 0 <= nu < w and grid.free[nv,nu] and labels[nv,nu] == 0:
                labels[nv,nu] = label
                heapq.heappush(queue, (distance+1, nv, nu, label))
    return labels


def manual_labels(grid, regions):
    labels = np.zeros(grid.image.shape, np.int32)
    for i, region in enumerate(regions, 1):
        polygon = np.asarray(region['polygon'], dtype=float)
        if polygon.ndim != 2 or polygon.shape[0] < 3 or polygon.shape[1] != 2 or not np.isfinite(polygon).all():
            raise ValueError('Each polygon requires at least 3 finite [u,v] pixel points.')
        mask = np.zeros(grid.image.shape, np.uint8)
        cv2.fillPoly(mask, [polygon.astype(np.int32)], 1)
        mask &= grid.free
        if np.any((labels > 0) & (mask > 0)):
            raise ValueError('Manual regions overlap in free space.')
        # Do not give one label to disconnected rooms across a wall.
        count, components, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        if count < 2:
            raise ValueError(f"Region {region['id']} has no free space.")
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        area = stats[largest, cv2.CC_STAT_AREA]
        if int(mask.sum()) - area > max(4, area * .05):
            raise ValueError(f"Region {region['id']} spans disconnected free areas.")
        mask = (components == largest).astype(np.uint8)
        labels[mask > 0] = i
    return labels


def generate(map_file, output, clearance=0.30, polygons=None, doorway=0.8, min_area=0.5):
    if clearance <= 0 or doorway <= 0 or min_area <= 0:
        raise ValueError('Clearance, doorway width and minimum area must be positive.')
    grid = MapData(map_file)
    definitions = yaml.safe_load(Path(polygons).read_text(encoding='utf-8'))['regions'] if polygons else None
    labels = manual_labels(grid, definitions) if definitions else automatic_labels(grid, doorway, min_area)
    regions = []
    preview = cv2.cvtColor(grid.image, cv2.COLOR_GRAY2BGR)
    rng = np.random.default_rng(7)
    for i in range(1, int(labels.max())+1):
        mask = labels == i
        safe = mask & (grid.clearance >= clearance)
        if not safe.any():
            raise ValueError(f'Region {i} has no goal with {clearance} m clearance.')
        # Maximize clearance from both walls and semantic boundaries.
        inside = cv2.distanceTransform(np.pad(mask.astype(np.uint8), 1), cv2.DIST_L2, 5)[1:-1,1:-1]
        score = np.where(safe, np.minimum(grid.clearance, inside*grid.resolution), -1)
        v, u = np.unravel_index(score.argmax(), score.shape)
        x, y = grid.pixel_to_world(int(u), int(v))
        base = definitions[i-1] if definitions else {'id': f'R{i}', 'name': f'Khu vực {i}'}
        regions.append({'id': str(base['id']), 'name': base['name'],
                        'aliases': base.get('aliases', []),
                        'goal': {'x': float(x), 'y': float(y), 'yaw': 0.0}})
        color = rng.integers(70, 240, size=3)
        preview[mask] = (0.45*preview[mask] + 0.55*color).astype(np.uint8)
        cv2.circle(preview, (int(u), int(v)), 4, (0,0,255), -1)
        cv2.putText(preview, str(base['id']), (int(u)+5,int(v)), cv2.FONT_HERSHEY_SIMPLEX, .55, (0,0,0), 2)
    if len(regions) < 3:
        raise ValueError('At least 3 regions are required.')
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {'frame_id': 'map', 'map': os.path.relpath(grid.path, output.parent), 'clearance': clearance, 'regions': regions}
    # Validate aliases, IDs and all goals before writing artifacts.
    from .commands import CommandParser
    CommandParser(regions)
    if len({r['id'] for r in regions}) != len(regions):
        raise ValueError('Duplicate region IDs.')
    output.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), encoding='utf-8')
    cv2.imwrite(str(output.with_suffix('.png')), preview)
    np.save(str(output.with_suffix('.labels.npy')), labels)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--polygons', help='YAML regions with pixel polygons [u,v]; origin top left.')
    parser.add_argument('--clearance', type=float, default=.30)
    parser.add_argument('--doorway-width', type=float, default=.8)
    parser.add_argument('--min-area', type=float, default=.5)
    args = parser.parse_args()
    try:
        data = generate(args.map, args.output, args.clearance, args.polygons, args.doorway_width, args.min_area)
    except (ValueError, KeyError, OSError, yaml.YAMLError) as error:
        parser.exit(1, f'Cannot segment map: {error}\n')
    print(f"Saved {len(data['regions'])} regions, preview PNG and labels.npy: {args.output}")


if __name__ == '__main__':
    main()
