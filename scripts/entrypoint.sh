#!/usr/bin/env bash
set -Eeuo pipefail
cd /app
source /app/scripts/usb-gadget.sh
declare -a child_pids=()

cleanup() {
    local status=$? pid iteration alive
    trap - EXIT INT TERM
    set +e
    for pid in "${child_pids[@]}"; do kill -TERM "$pid" 2>/dev/null; done
    for ((iteration=0; iteration<50; iteration++)); do
        alive=0
        for pid in "${child_pids[@]}"; do
            kill -0 "$pid" 2>/dev/null && alive=1
        done
        (( alive )) || break
        sleep 0.1
    done
    for pid in "${child_pids[@]}"; do
        kill -KILL "$pid" 2>/dev/null
        wait "$pid" 2>/dev/null
    done
    gadget_cleanup || status=1
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

gadget_setup
/usr/local/bin/oak-webcam-bridge --socket "${OAK_WEBCAM_SOCKET:-/tmp/oak-webcam.sock}" --function "$FUNCTION" &
child_pids+=("$!")
python3.12 -u /app/main.py &
child_pids+=("$!")
# Any child exit stops the other process and restores the USB gadget.
status=0
wait -n "${child_pids[@]}" || status=$?
echo "Webcam worker exited (status $status); stopping app." >&2
exit "$status"
