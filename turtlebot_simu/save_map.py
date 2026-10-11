"""Save the current occupancy grid as a Nav2-compatible YAML/PGM pair."""

import argparse
import math
from pathlib import Path
import subprocess
import sys


def map_prefix(value: str) -> Path:
    """Return an absolute map prefix, accepting accidental .yaml/.pgm suffixes."""
    path = Path(value).expanduser()
    if path.suffix.lower() in {'.yaml', '.yml', '.pgm'}:
        path = path.with_suffix('')
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Save /map using nav2_map_server/map_saver_cli.',
    )
    parser.add_argument(
        '--output', '-o', required=True,
        help='Output prefix, for example ~/tb4_ws/src/turtlebot_simu/maps/map',
    )
    parser.add_argument(
        '--timeout', type=float, default=10.0,
        help='Seconds to wait for a map message (default: 10)',
    )
    parser.add_argument('--map-topic', default='/map', help='Map topic, e.g. /robot/map')
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')

    output = map_prefix(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        'ros2', 'run', 'nav2_map_server', 'map_saver_cli',
        '-f', str(output),
        '--fmt', 'pgm',
        '--ros-args',
        '-p', 'map_subscribe_transient_local:=true',
        '-p', f'save_map_timeout:={args.timeout}',
        '-r', f'map:={args.map_topic}',
    ]

    print(f'Saving map to {output}.yaml and {output}.pgm ...')
    completed = subprocess.run(command, check=False)
    yaml_file = output.with_suffix('.yaml')
    pgm_file = output.with_suffix('.pgm')

    if completed.returncode != 0 or not yaml_file.is_file() or not pgm_file.is_file():
        print(
            'Map saving failed. Check that SLAM is running and /map is publishing.',
            file=sys.stderr,
        )
        raise SystemExit(completed.returncode or 1)

    print(f'Map saved successfully: {yaml_file} and {pgm_file}')
