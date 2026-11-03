#!/usr/bin/env bash
# Build the last Humble release before the TF MessageFilter deadlock regression.
# Keep this overlay local; do not downgrade packages in /opt/ros/humble.
set -eo pipefail
seman_package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
seman_compat_dir="$seman_package_dir/.compat/tf2"
seman_tf2_revision=518e0801d419ba1bcb24cfbe039a99903fd2d710
if [[ "${ROS_DISTRO:-}" != humble ]]; then
    echo 'Activate ROS 2 Humble and Python 3.10 first (scripts/activate_hri.bash).' >&2
    exit 1
fi
mkdir -p "$seman_compat_dir"
touch "$seman_package_dir/.compat/COLCON_IGNORE"
if [[ ! -d "$seman_compat_dir/src/.git" ]]; then
    git clone --depth 1 --branch 0.25.20 https://github.com/ros2/geometry2.git "$seman_compat_dir/src"
fi
if [[ "$(git -C "$seman_compat_dir/src" rev-parse HEAD)" != "$seman_tf2_revision" ]]; then
    echo 'Unexpected geometry2 revision; use a clean 0.25.20 checkout.' >&2
    exit 1
fi
python -m colcon --log-base "$seman_compat_dir/log" build \
    --base-paths "$seman_compat_dir/src" \
    --build-base "$seman_compat_dir/build" \
    --install-base "$seman_compat_dir/install" \
    --packages-select tf2 tf2_ros --packages-ignore tf2_msgs \
    --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo -DBUILD_TESTING=OFF \
    "-DPython3_EXECUTABLE=$(command -v python)"
echo "TF2 compatibility overlay built. Source scripts/activate_hri.bash again."
