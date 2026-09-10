#!/usr/bin/env bash
# Sourced by entrypoint.sh. Only paths created by this process are removed.
GADGET=/sys/kernel/config/usb_gadget/g1
FUNCTION=uvc.oakwebcam
FUNCTION_PATH="$GADGET/functions/$FUNCTION"
CONFIG_PATH="$GADGET/configs/c.1"
PRODUCT_PATH="$GADGET/strings/0x409/product"
declare -a gadget_paths=() gadget_kinds=()
gadget_changed=0
original_udc=
original_product=

# RVC4 USB management can rebind immediately after an unbind. Match the
# reference's bounded settling window, but never displace another controller.
gadget_unbind() {
    local attempt current
    for ((attempt=1; attempt<=10; attempt++)); do
        current=$(<"$GADGET/UDC")
        if [[ -n "$current" && "$current" != "$original_udc" ]]; then
            echo "USB ownership changed to $current; refusing to unbind it." >&2
            return 1
        fi
        printf '\n' > "$GADGET/UDC" || return 1
        sleep 0.1
        if [[ -z "$(<"$GADGET/UDC")" ]]; then
            sleep 0.1
            [[ -z "$(<"$GADGET/UDC")" ]] && return 0
        fi
    done
    echo "USB controller did not remain unbound after 10 attempts (current: $(<"$GADGET/UDC"))." >&2
    return 1
}

gadget_mkdir() {
    mkdir "$1"
    gadget_paths+=("$1")
    gadget_kinds+=(directory)
}

gadget_link() {
    # configfs resolves relative targets against the caller's working directory,
    # unlike ordinary filesystem symlinks. Run in the link's parent directory.
    (cd -- "$(dirname -- "$2")" && ln -s "$1" "$(basename -- "$2")")
    gadget_paths+=("$2")
    gadget_kinds+=(link)
}

gadget_setup() {
    local existing target controller
    [[ -d "$CONFIG_PATH" && -r "$GADGET/UDC" && -r "$PRODUCT_PATH" ]] || {
        echo 'Expected existing OAK4 USB gadget g1/configs/c.1 and English product string.' >&2
        return 1
    }
    [[ ! -e "$FUNCTION_PATH" ]] || {
        echo "Existing app-owned function: $FUNCTION_PATH. Inspect its previous owner first." >&2
        return 1
    }
    # Factory images may contain unused UVC functions. Preserve them; only an
    # actively linked camera conflicts with exposing one webcam interface.
    for existing in "$GADGET"/configs/*/*; do
        [[ -L "$existing" ]] || continue
        target=$(readlink -f -- "$existing")
        if [[ "$target" == "$GADGET"/functions/uvc.* ]]; then
            echo "Active UVC function: $existing. Stop its owning app first." >&2
            return 1
        fi
    done
    original_udc=$(<"$GADGET/UDC")
    original_product=$(<"$PRODUCT_PATH")
    # Require an existing binding: do not guess among controllers or seize one.
    [[ -n "$original_udc" ]] || {
        echo 'Existing USB gadget is unbound; configure the OAK4 USB connection first.' >&2
        return 1
    }
    controller="$original_udc"
    gadget_changed=1
    gadget_unbind || return 1
    gadget_mkdir "$FUNCTION_PATH"
    gadget_mkdir "$FUNCTION_PATH/streaming/mjpeg/m"
    gadget_mkdir "$FUNCTION_PATH/streaming/mjpeg/m/1080p"
    printf '1920\n' > "$FUNCTION_PATH/streaming/mjpeg/m/1080p/wWidth"
    printf '1080\n' > "$FUNCTION_PATH/streaming/mjpeg/m/1080p/wHeight"
    printf '4147200\n' > "$FUNCTION_PATH/streaming/mjpeg/m/1080p/dwMaxVideoFrameBufferSize"
    printf '333333\n' > "$FUNCTION_PATH/streaming/mjpeg/m/1080p/dwFrameInterval"
    printf '333333\n' > "$FUNCTION_PATH/streaming/mjpeg/m/1080p/dwDefaultFrameInterval"
    gadget_mkdir "$FUNCTION_PATH/streaming/header/h"
    gadget_link ../../mjpeg/m "$FUNCTION_PATH/streaming/header/h/m"
    gadget_link ../../header/h "$FUNCTION_PATH/streaming/class/fs/h"
    gadget_link ../../header/h "$FUNCTION_PATH/streaming/class/hs/h"
    gadget_link ../../header/h "$FUNCTION_PATH/streaming/class/ss/h"
    gadget_mkdir "$FUNCTION_PATH/control/header/h"
    gadget_link ../../header/h "$FUNCTION_PATH/control/class/fs/h"
    gadget_link ../../header/h "$FUNCTION_PATH/control/class/ss/h"
    printf '3072\n' > "$FUNCTION_PATH/streaming_maxpacket"
    gadget_link "../../functions/$FUNCTION" "$CONFIG_PATH/$FUNCTION"
    printf 'OAK4 Webcam\n' > "$PRODUCT_PATH"
    printf '%s\n' "$controller" > "$GADGET/UDC"
    [[ "$(<"$GADGET/UDC")" == "$controller" ]] || {
        echo 'Failed to bind webcam USB configuration.' >&2
        return 1
    }
}

gadget_cleanup() {
    local index failed=0 current_udc
    (( gadget_changed )) || return 0
    current_udc=$(<"$GADGET/UDC")
    if [[ -n "$current_udc" ]]; then
        # A different controller signals external ownership; do not displace it.
        if [[ "$current_udc" != "$original_udc" ]]; then
            echo 'USB ownership changed externally; manual cleanup of uvc.oakwebcam required.' >&2
            return 1
        fi
        gadget_unbind || return 1
    fi
    for ((index=${#gadget_paths[@]}-1; index>=0; index--)); do
        if [[ "${gadget_kinds[index]}" == link ]]; then
            rm -- "${gadget_paths[index]}" || failed=1
        else
            rmdir -- "${gadget_paths[index]}" || failed=1
        fi
    done
    printf '%s\n' "$original_product" > "$PRODUCT_PATH" || failed=1
    printf '%s\n' "$original_udc" > "$GADGET/UDC" || failed=1
    [[ "$(<"$GADGET/UDC")" == "$original_udc" ]] || failed=1
    (( failed == 0 )) || echo 'USB cleanup incomplete; inspect app logs and uvc.oakwebcam.' >&2
    return "$failed"
}
