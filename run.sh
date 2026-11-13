#!/usr/bin/env bash
# Bai 8: activate the existing Conda hri environment, build, and run Gazebo + webcam.
set -eo pipefail

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_deps=false
check_only=false
build_only=false
launch_args=()
for arg in "$@"; do
    case "$arg" in
        --install-deps) install_deps=true ;;
        --check) check_only=true ;;
        --build-only) build_only=true ;;
        -h|--help)
            cat <<'HELP'
Bai 8 - TurtleBot 4 simulation controlled by webcam emotions, Conda hri.
Usage: ./run.sh [--install-deps] [--check|--build-only] [ROS launch arguments]
  --install-deps  Install the exercise's Python dependencies into hri.
  --check         Check environment/dependencies, then exit without starting sim.
  --build-only    Build the package, then exit without starting sim.
Examples:
  ./run.sh --install-deps
  ./run.sh camera_index:=1
  ./run.sh headless:=true recognition:=false
Environment: CONDA_ENV_NAME (default hri), CONDA_SH, ROS_SETUP,
             BAI8_WORKSPACE (default .run_ws beside this script).
HELP
            exit 0 ;;
        --*) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
        *) launch_args+=("$arg") ;;
    esac
done

fail() { printf 'Bai 8: %s\n' "$*" >&2; exit 1; }
conda_sh="${CONDA_SH:-}"
if [[ -z "$conda_sh" ]]; then
    if [[ -n "${CONDA_EXE:-}" && -x "$CONDA_EXE" ]]; then
        conda_sh="$("$CONDA_EXE" info --base)/etc/profile.d/conda.sh"
    elif command -v conda >/dev/null 2>&1; then
        conda_sh="$(conda info --base)/etc/profile.d/conda.sh"
    else
        for candidate in "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/miniforge3"; do
            if [[ -f "$candidate/etc/profile.d/conda.sh" ]]; then
                conda_sh="$candidate/etc/profile.d/conda.sh"
                break
            fi
        done
    fi
fi
[[ -f "$conda_sh" ]] || fail 'Cannot find conda.sh; set CONDA_SH to its full path.'
source "$conda_sh"
conda activate "${CONDA_ENV_NAME:-hri}"
ros_setup="${ROS_SETUP:-/opt/ros/humble/setup.bash}"
[[ -f "$ros_setup" ]] || fail "Missing ROS 2 setup: $ros_setup"
source "$ros_setup"
# Avoid importing unrelated packages from ~/.local into the existing hri env.
export PYTHONNOUSERSITE=1
export DEEPFACE_BACKEND_ENGINE=onnx
export ROS_LOCALHOST_ONLY=1
hri_python="$CONDA_PREFIX/bin/python"
"$hri_python" - <<'PY'
import sys
if sys.version_info[:2] != (3, 10):
    raise SystemExit('ROS 2 Humble on Ubuntu 22.04 requires Python 3.10 in hri.')
print('Bai 8 Python:', sys.executable, flush=True)
PY
if "$install_deps"; then
    "$hri_python" -m pip install -r "$PACKAGE_DIR/requirements.txt"
    # DeepFace requests headless OpenCV. Use the GUI contrib build from the
    # runtime requirements instead, so the webcam window remains available.
    "$hri_python" -m pip install --no-deps -r "$PACKAGE_DIR/requirements-models.txt"
fi
# A simulation-only launch does not need the webcam model, but normal runs do.
need_vision=true
for arg in "${launch_args[@]}"; do
    [[ "$arg" != recognition:=false ]] || need_vision=false
done
"$hri_python" - "$need_vision" <<'PY'
import importlib
import sys
from ament_index_python.packages import get_package_share_directory
modules = ['rclpy', 'geometry_msgs.msg', 'colcon_core', 'setuptools']
if sys.argv[1] == 'true':
    modules += ['cv2', 'mediapipe', 'onnxruntime', 'deepface.DeepFace']
for name in modules:
    try:
        importlib.import_module(name)
    except Exception as exc:
        raise SystemExit(f'{name}: {exc}\nRun ./run.sh --install-deps --check to install Python dependencies in hri.')
for package in ('turtlebot4_description', 'irobot_create_description',
                'irobot_create_control', 'ign_ros2_control', 'controller_manager',
                'joint_state_broadcaster', 'diff_drive_controller',
                'robot_state_publisher', 'xacro', 'ros_gz_sim', 'ros_gz_bridge'):
    try:
        get_package_share_directory(package)
    except Exception:
        raise SystemExit(f'Missing ROS package: {package}. See README installation command.')
if sys.argv[1] == 'true':
    import cv2
    if 'GUI:                           NONE' in cv2.getBuildInformation():
        raise SystemExit('OpenCV lacks GUI support; reinstall the GUI opencv-contrib-python from requirements.txt.')
print('Bai 8 environment: OK', flush=True)
PY
if "$check_only"; then exit 0; fi
workspace="${BAI8_WORKSPACE:-$PACKAGE_DIR/.run_ws}"
mkdir -p "$workspace"
workspace="$(cd -- "$workspace" && pwd)"
touch "$workspace/COLCON_IGNORE"
# Colcon's Python interpreter determines the installed entry-point shebang.
"$hri_python" -m colcon --log-base "$workspace/log" build \
    --base-paths "$PACKAGE_DIR" --packages-select ttbot4_face_emote \
    --build-base "$workspace/build" --install-base "$workspace/install" --symlink-install
source "$workspace/install/setup.bash"
if "$build_only"; then exit 0; fi
exec "$hri_python" /opt/ros/humble/bin/ros2 launch \
    ttbot4_face_emote face_emote.launch.py "${launch_args[@]}"
