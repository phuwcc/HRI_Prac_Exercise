#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: run_no_mic.sh [rviz:=false] [extra launch arguments]'
    exit 0
fi
activate_project
run_coursework speech:=false "$@"
