#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: undock.sh (run after Nav2 is ready; wait for SUCCEEDED)'
    exit 0
fi
activate_project
exec ros2 action send_goal /undock irobot_create_msgs/action/Undock '{}' --feedback
