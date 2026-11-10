#!/usr/bin/env bash
set -eo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.bash"
if [[ "${1:-}" == --help ]]; then
    echo 'Usage: run_mic.sh [microphone:="USB Audio"] [whisper_model:=base.en] [extra launch arguments]'
    exit 0
fi
activate_project
run_coursework speech:=true "$@"
