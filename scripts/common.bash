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
