#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: run_no_mic.sh [rviz:=false] [extra launch arguments]'
    exit 0
fi
activate_project
exec ros2 launch ttbot4_seman_nav coursework.launch.py \
    "regions:=$seman_repo_dir/config/regions_small_room.yaml" speech:=false "$@"
