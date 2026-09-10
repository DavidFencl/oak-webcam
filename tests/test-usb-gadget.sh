#!/usr/bin/env bash
# Host-only configfs simulation. Never accesses /sys or a connected device.
set -Eeuo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test_root=$(mktemp -d /tmp/oak-webcam-gadget-test.XXXXXX)
trap '[[ "$test_root" == /tmp/oak-webcam-gadget-test.* ]] && rm -rf -- "$test_root"' EXIT
source "$script_dir/../scripts/usb-gadget.sh"

prepare_case() {
    gadget_paths=()
    gadget_kinds=()
    gadget_changed=0
    original_udc=
    original_product=
    GADGET="$test_root/$1/g1"
    FUNCTION_PATH="$GADGET/functions/$FUNCTION"
    CONFIG_PATH="$GADGET/configs/c.1"
    PRODUCT_PATH="$GADGET/strings/0x409/product"
    command mkdir -p "$CONFIG_PATH" "$GADGET/functions/uvc.0" \
        "$GADGET/functions/ncm.usb0" "$GADGET/strings/0x409"
    printf 'factory-controller\n' > "$GADGET/UDC"
    printf 'Factory OAK\n' > "$PRODUCT_PATH"
    command ln -s ../../functions/ncm.usb0 "$CONFIG_PATH/ncm.usb0"
    fail_link=0
}

# Emulate only configfs automatic contents. Scripts still perform their actual
# setup, path tracking, conflict checks and restoration against regular files.
mkdir() {
    command mkdir "$@"
    if [[ "$1" == "$FUNCTION_PATH" ]]; then
        command mkdir -p "$1/streaming/mjpeg" "$1/streaming/header" \
            "$1/streaming/class/fs" "$1/streaming/class/hs" "$1/streaming/class/ss" \
            "$1/control/header" "$1/control/class/fs" "$1/control/class/ss"
        : > "$1/streaming_maxpacket"
    elif [[ "$1" == "$FUNCTION_PATH/streaming/mjpeg/m/1080p" ]]; then
        local attribute
        for attribute in wWidth wHeight dwMaxVideoFrameBufferSize dwFrameInterval dwDefaultFrameInterval; do
            : > "$1/$attribute"
        done
    fi
}

ln() {
    if (( fail_link )) && [[ "${@: -1}" == "$FUNCTION_PATH/streaming/class/hs/h" ]]; then
        echo 'Injected configfs link failure' >&2
        return 42
    fi
    command ln "$@"
}

rmdir() {
    local path="${@: -1}" attribute
    if [[ "$path" == "$FUNCTION_PATH/streaming/mjpeg/m/1080p" ]]; then
        for attribute in wWidth wHeight dwMaxVideoFrameBufferSize dwFrameInterval dwDefaultFrameInterval; do
            command rm -- "$path/$attribute"
        done
    elif [[ "$path" == "$FUNCTION_PATH" ]]; then
        command rm -- "$path/streaming_maxpacket"
        command rmdir "$path/streaming/mjpeg" "$path/streaming/header" \
            "$path/streaming/class/fs" "$path/streaming/class/hs" "$path/streaming/class/ss" \
            "$path/control/header" "$path/control/class/fs" "$path/control/class/ss" \
            "$path/streaming/class" "$path/control/class" "$path/streaming" "$path/control"
    fi
    command rmdir "$@"
}

assert_restored() {
    [[ "$(<"$GADGET/UDC")" == factory-controller ]]
    [[ "$(<"$PRODUCT_PATH")" == 'Factory OAK' ]]
    [[ ! -e "$FUNCTION_PATH" && ! -L "$CONFIG_PATH/$FUNCTION" ]]
    [[ -d "$GADGET/functions/uvc.0" ]]
    [[ "$(readlink "$CONFIG_PATH/ncm.usb0")" == ../../functions/ncm.usb0 ]]
}

prepare_case success
gadget_setup
[[ "$(<"$PRODUCT_PATH")" == 'OAK4 Webcam' ]]
[[ "$(<"$GADGET/UDC")" == factory-controller ]]
[[ "$(readlink -f "$CONFIG_PATH/$FUNCTION")" == "$FUNCTION_PATH" ]]
[[ "$(readlink -f "$FUNCTION_PATH/control/class/fs/h")" == "$FUNCTION_PATH/control/header/h" ]]
[[ "$(<"$FUNCTION_PATH/streaming/mjpeg/m/1080p/wWidth")" == 1920 ]]
gadget_cleanup
assert_restored
echo 'PASS successful setup/cleanup preserves unused factory UVC and active NCM'

prepare_case conflict
command ln -s ../../functions/uvc.0 "$CONFIG_PATH/factory-camera"
if gadget_setup; then
    echo 'FAIL active UVC accepted' >&2
    exit 1
fi
[[ "$gadget_changed" == 0 ]]
[[ ${#gadget_paths[@]} == 0 ]]
assert_restored
[[ -L "$CONFIG_PATH/factory-camera" ]]
echo 'PASS active UVC rejected before mutations'

prepare_case partial_failure
fail_link=1
# EXIT cleanup runs with errexit disabled, as it does in the entrypoint.
set +e
(
    set -e
    trap 'status=$?; set +e; gadget_cleanup; exit "$status"' EXIT
    gadget_setup
)
status=$?
set -e
[[ "$status" == 42 ]]
assert_restored
echo 'PASS partial setup failure removes only created paths and restores USB state'
