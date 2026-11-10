#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: build.sh [extra colcon build arguments]'
    exit 0
fi
activate_project
exec python -m colcon --log-base log_seman build \
    --build-base build_seman --install-base install_seman \
    --packages-select turtlebot_simu ttbot4_seman_nav --symlink-install "$@"
