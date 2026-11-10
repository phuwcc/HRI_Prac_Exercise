#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: check_logic.sh [extra pytest arguments]'
    echo 'Tests parser, audio detection and navigation with a mock Nav2 server; no Gazebo/microphone.'
    exit 0
fi
activate_project
# Keep mock action servers separate from the running simulator/robot.
export ROS_DOMAIN_ID="${SEMAN_TEST_DOMAIN_ID:-86}"
exec python -m pytest "$seman_repo_dir/test" -q "$@"
