#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: status.sh (Ctrl+C to stop watching navigation status)'
    exit 0
fi
activate_project
exec ros2 topic echo /semantic/status
