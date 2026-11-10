#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
case "${1:-list}" in
    list|--help|-h)
        cat <<'HELP'
Usage: send_command.sh PRESET
       send_command.sh "Go to the laboratory."

Presets (send one at a time; wait for the previous task to finish):
  a        Go to area A.                  -> A
  b        Go to area B.                  -> B
  c        Go to area C.                  -> C
  ab       Go from area A to area B.      -> A then B
  acb      Go from A via C then to B.     -> A then C then B
  lab      Go to the laboratory.          -> B
  invalid  Go to area Z.                  -> rejected, no movement
  stop     Stop.                         -> request navigation cancellation
HELP
        exit 0 ;;
    a) seman_command='Go to area A.' ;;
    b) seman_command='Go to area B.' ;;
    c) seman_command='Go to area C.' ;;
    ab) seman_command='Go from area A to area B.' ;;
    acb) seman_command='Go from A via C then to B.' ;;
    lab) seman_command='Go to the laboratory.' ;;
    invalid) seman_command='Go to area Z.' ;;
    stop) seman_command='Stop.' ;;
    -*) echo 'Unknown option; use --help.' >&2; exit 2 ;;
    *) seman_command="$*" ;;
esac
activate_project
# JSON is valid YAML; serialize instead of interpolating user text into YAML.
seman_payload="$(python -c 'import json, sys; print(json.dumps({"data": sys.argv[1]}))' "$seman_command")"
echo "Sending: $seman_command"
exec ros2 topic pub --once /voice/command std_msgs/msg/String "$seman_payload"
