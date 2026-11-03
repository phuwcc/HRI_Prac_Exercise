"""Check the TF libraries before starting a simulation with Nav2."""
from pathlib import Path
import xml.etree.ElementTree as ET


def check_tf2_versions(versions):
    # These Humble releases can deadlock a TransformListener against a
    # MessageFilter, freezing AMCL/costmaps even while /tf remains live.
    # https://github.com/ros2/geometry2/issues/995
    affected = {'tf2': {'0.25.21', '0.25.22', '0.25.23'},
                'tf2_ros': {'0.25.23'}}
    broken = [f'{package}={version}' for package, version in versions.items()
              if version in affected.get(package, set())]
    if broken:
        raise RuntimeError(
            f'Unsupported TF2 runtime ({", ".join(broken)}): known MessageFilter deadlock. '
            'From the workspace root, activate hri, run '
            '`bash ttbot4_seman_nav/scripts/setup_tf2_compat.bash`, then source '
            '`ttbot4_seman_nav/scripts/activate_hri.bash` again. '
            'This builds a local 0.25.20 overlay without changing system ROS packages.'
        )


def validate_tf2_runtime():
    from ament_index_python.packages import get_package_share_directory
    versions = {}
    for package in ('tf2', 'tf2_ros'):
        manifest = Path(get_package_share_directory(package)) / 'package.xml'
        versions[package] = ET.parse(manifest).getroot().findtext('version')
    check_tf2_versions(versions)
