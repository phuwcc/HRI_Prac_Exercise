# Shared setup for the executable .sh scripts. Source this file; do not run it.
seman_scripts_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
seman_repo_dir="$(dirname -- "$seman_scripts_dir")"
seman_workspace_dir="$(dirname -- "$seman_repo_dir")"

activate_project() {
    # ROS/Conda setup files are not compatible with bash nounset.
    cd -- "$seman_workspace_dir"
    source "$seman_scripts_dir/activate_hri.bash"
    set -u
    if [[ "$(python -c 'import sys; print("%d.%d" % sys.version_info[:2])')" != 3.10 ]]; then
        echo 'ROS Humble requires Python 3.10 in the hri environment.' >&2
        exit 1
    fi
}

run_coursework() {
    # A separate Gazebo partition cannot isolate ROS topics/action servers.
    # Reject a second script launch on the same ROS domain before spawning it.
    local seman_lock_dir="${XDG_RUNTIME_DIR:-/tmp}"
    local seman_lock_file="$seman_lock_dir/semantic_nav_${UID}_${ROS_DOMAIN_ID:-0}.lock"
    if ! command -v flock >/dev/null 2>&1; then
        echo 'Missing flock (install util-linux).' >&2
        exit 1
    fi
    # Keep the descriptor only in the supervising flock process: an orphaned
    # Gazebo must not keep the lock after the launch process has exited.
    local seman_launch_status
    if flock --nonblock --close --conflict-exit-code 75 "$seman_lock_file" \
        ros2 launch ttbot4_seman_nav coursework.launch.py \
        "regions:=$seman_repo_dir/config/regions_small_room.yaml" "$@"; then
        return 0
    else
        seman_launch_status=$?
        if [[ "$seman_launch_status" == 75 ]]; then
            echo 'A navigation script is already running on this ROS domain. Stop it with Ctrl+C first.' >&2
        fi
        return "$seman_launch_status"
    fi
}
