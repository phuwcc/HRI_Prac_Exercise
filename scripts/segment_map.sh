#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
seman_mode="${1:-manual}"
if [[ "$seman_mode" == --help ]]; then
    echo 'Usage: segment_map.sh [manual|auto] [extra segment_map arguments]'
    echo 'Writes regions YAML, preview PNG and labels.npy. Use --output to choose another path.'
    exit 0
fi
if (($#)); then shift; fi
case "$seman_mode" in
    manual)
        seman_segment_args=(--polygons "$seman_repo_dir/config/polygons_small_room.yaml"
                            --output "$seman_repo_dir/config/regions_small_room.yaml") ;;
    auto)
        seman_segment_args=(--output "$seman_repo_dir/config/regions_auto.yaml"
                            --doorway-width .8 --min-area .5 --clearance .30) ;;
    *) echo 'Expected manual or auto; use --help.' >&2; exit 2 ;;
esac
activate_project
exec ros2 run ttbot4_seman_nav segment_map \
    --map "$seman_workspace_dir/turtlebot_simu/maps/small_room.yaml" \
    "${seman_segment_args[@]}" "$@"
