#!/usr/bin/env bash
set -Eeuo pipefail
cd /app
# Resolve/validate the preset before any USB mutation. No eval of shell output.
usb_mode=$(python3.12 -m presets.config --usb)
read -r OAK_WEBCAM_WIDTH OAK_WEBCAM_HEIGHT OAK_WEBCAM_FPS <<< "$usb_mode"
export OAK_WEBCAM_WIDTH OAK_WEBCAM_HEIGHT OAK_WEBCAM_FPS
if [[ "${OAK_WEBCAM_PRESET:-face-attention}" == face-attention ]]; then
    # Model download/initialization must not consume the bridge's first-frame timeout.
    python3.12 -m presets.models
fi
source /app/scripts/usb-gadget.sh
declare -a child_pids=()
runtime_dir=

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
    if [[ -n "$runtime_dir" ]]; then
        rm -f -- "$runtime_dir/frame.sock"
        rmdir -- "$runtime_dir"
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A reboot can leave a socket inode in the persistent container filesystem.
# Each normal run owns a fresh directory, without unlinking another run's socket.
if [[ -z "${OAK_WEBCAM_SOCKET:-}" ]]; then
    runtime_dir=$(mktemp -d /tmp/oak-webcam.XXXXXX)
    export OAK_WEBCAM_SOCKET="$runtime_dir/frame.sock"
fi
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
