# OAK4 Webcam

Run a Python DepthAI pipeline on an OAK4 D Pro and send its selected video output to your computer as a native USB UVC webcam. The app advertises **OAK4 Webcam**, MJPEG, 1920 × 1080 at 30 FPS. There is no host virtual-camera driver or video relay service.

Verified on OAK4-D R7 / Luxonis OS 1.40.0 with Fedora: USB webcam enumeration and capture/decode of 60 frames at 1920 × 1080, approximately 30 FPS. Long-running use and Discord/Meet/OBS compatibility still require application-level validation.

The development app now builds and runs on the connected OAK4. A distributable `.oakapp` package has not been generated. Device internet and a correct clock are required when fetching build dependencies.

## Hardware and deployment

Use a USB data cable between the OAK4 and computer, and a power arrangement that meets the OAK4 D Pro requirements. A computer USB port alone may not provide sufficient power. Prefer Ethernet for device management: starting and stopping this app briefly disconnects the composite USB device while its webcam interface changes. Stop any other app using the cameras before starting this one.

From this directory, with `oakctl` installed and the device reachable (replace `DEVICE_IP`):

```bash
oakctl device list
oakctl app run . -d DEVICE_IP
```

For a reusable package:

```bash
oakctl app build . -d DEVICE_IP
oakctl app install ./PACKAGE.oakapp -d DEVICE_IP --enable false
```

Replace `PACKAGE.oakapp` with the actual generated filename. Installation starts the app and, by default, stops and disables other apps; the example disables automatic startup of this app for initial testing. Inspect and stop it with:

```bash
oakctl app list -d DEVICE_IP
oakctl app logs APP_ID -d DEVICE_IP
oakctl app stop APP_ID -d DEVICE_IP
```

Use the ID returned by `app list`; a source development run uses `00000000-0000-0000-0000-000000000000`.

## Customize the pipeline

Edit `pipeline.py`, keeping this public function:

```python
def build_pipeline(pipeline):
    # Create DepthAI v3 nodes, link them, and return one image output.
    return selected_image_output
```

The runtime creates and starts the pipeline, consumes this one selected output and encodes it as MJPEG. Your function must return a DepthAI image output producing **1920 × 1080 NV12 frames at 30 FPS**. It must not start the pipeline or open another device. The default implementation selects RGB; its source is the working customization example. Internal branches may do other processing, but only the returned image output becomes webcam video. Render depth maps, annotations or detections into a compatible image before returning their output. Rebuild/re-run the app after editing Python.

The first version has a fixed USB mode. Changing the image size or frame rate in Python alone does not change the USB descriptors. USB frames must fit the 4,147,200-byte maximum; oversized or malformed data must not be truncated. Audio, host camera controls and additional video modes are outside this version's contract.

## Select the camera

- Discord: User Settings → Voice & Video → Camera → OAK4 Webcam.
- Google Meet: Settings → Video → Camera → OAK4 Webcam; allow browser camera access.
- OBS: add a Video Capture Device source and select OAK4 Webcam. If manual settings are necessary, choose MJPEG, 1920 × 1080, 30 FPS.

Names and menu wording can vary by host OS; a composite device may be shown under a generic USB camera name. Test each application separately and close other consumers before switching.

## Lifecycle and recovery

The app extends the existing `g1/configs/c.1` USB gadget with its own `uvc.oakwebcam` function. It preserves existing functions, including unused factory UVC functions, and restores the original product string and controller binding on normal exit, initialization failure and handled stop signals. It refuses to start when a UVC function is already linked into a USB configuration or its own function already exists. It allows up to ten unbind attempts with settling checks for transient RVC4 rebinding and refuses to displace a different controller.

Stopping either the Python runtime or native bridge stops the other process. SIGKILL, power loss and container teardown without a graceful stop cannot run cleanup. If a later start reports a leftover UVC function, inspect the previous app's logs and stop its owning process; do not delete unrelated USB gadget state. A device reboot can restore the OS-managed USB setup after an unclean termination, but is an operator recovery action.

## Validation still required

On a real OAK4 and host, verify camera enumeration, decoded moving 1080p frames, a visible Python pipeline change, and live video in all three consumers. Open/close/reopen the camera and stop/restart the app; confirm existing USB management functions remain available after cleanup. Capture evidence under `evidence/`. A still preview or running process is insufficient to prove delivery.

The implementation follows the Luxonis `oak-examples/cpp/uvc` gadget topology and pinned `uvc-gadget` dependency. Python defines the pipeline; the native bridge transports length-prefixed MJPEG over a local Unix socket and handles UVC/V4L2. No DepthAI C++ source build is required.

## Local checks

From the project directory with Python and CMake available:

```bash
python -m unittest discover -s tests -v
bash tests/test-usb-gadget.sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

Native and Python transport tests require local Unix socket access. The USB lifecycle tests emulate configfs and never modify device USB state. Local native compilation targets the host; oakctl builds the ARM64 app on the OAK4.
