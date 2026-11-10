#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: run_mic.sh [microphone:="USB Audio"] [whisper_model:=base.en] [extra launch arguments]'
    exit 0
fi
activate_project
exec ros2 launch ttbot4_seman_nav coursework.launch.py \
    "regions:=$seman_repo_dir/config/regions_small_room.yaml" speech:=true "$@"
