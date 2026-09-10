# OAK4 Webcam

Run a Python DepthAI pipeline on OAK4 D Pro and expose its output as **OAK4 Webcam**, a native MJPEG USB camera for Discord, Google Meet or OBS. Processing runs on the OAK; no host virtual-camera driver is needed.

## Prepared presets

| Preset | USB mode | Content |
| --- | --- | --- |
| `rgb-1080p` | 1920 × 1080, 30 FPS | Original RGB webcam |
| `rgb-4k` | 3840 × 2160, 30 FPS | Native 4K RGB |
| `lens-xl` | 3840 × 2160, 30 FPS | LENS XL 1248 × 780 depth visualization, about 9 new frames/s |
| `nas` | 3840 × 2160, 30 FPS | Neural Assisted Stereo depth visualization, 30 FPS requested |
| `pointcloud` | 3840 × 2160, 30 FPS | RGB-colored NAS metric points, fixed view rendered at 720p |
| `pointcloud-depth` | 3840 × 2160, 30 FPS | Depth-colored NAS metric points, fixed view rendered at 720p |
| `face-attention` (default) | 3840 × 2160, 30 FPS | Facial-expression and head-direction overlay, 1280 × 720 input at 20 FPS |
| `custom` | 3840 × 2160, 30 FPS initially | Trusted `.py` file exposing `build_pipeline(pipeline)` |

USB FPS is the advertised mode. Depth/model computation and USB bandwidth determine fresh-frame delivery; an upscaled output adds no source detail. The bridge can repeat its latest complete frame.

See [preset usage and interpretation](docs/presets.md) for commands, model details, expected performance, and customization.

## Run or switch

Connect USB data and adequate power. Prefer Ethernet for device management because app startup/shutdown briefly disconnects the composite USB device. Stop the current camera owner first; do not run multiple pipelines against one OAK.

```bash
oakctl device list
oakctl app list -d DEVICE_IP
# Stop this project's existing development app if it is running:
oakctl app stop 00000000-0000-0000-0000-000000000000 -d DEVICE_IP
# Choose any preset name from the table:
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=face-attention
oakctl app logs 00000000-0000-0000-0000-000000000000 -d DEVICE_IP --no-follow
```

Replace `DEVICE_IP` with the current address or serial shown by discovery. Source development runs use the all-zero app ID. If another app owns the camera, stop that app explicitly before running this one. `--detach` returns before startup finishes: check logs and the actual video output. Reopen the camera in the consumer after restarting the app, especially when changing resolution.

Open the console URL printed in the startup log (`http://DEVICE_IP:8080/#token=...`) to preview video and switch presets without restarting the app or disconnecting USB. The initial preset fixes the session USB mode; later presets are resized to it. See [console usage and API](docs/control-panel.md) and [fixed point-cloud view settings](docs/pointcloud.md).

For a custom pipeline, place the file in this repository before deployment, choose `custom` in the console, and enter its OAK-side path such as `/app/examples/custom_rgb.py`. Custom code must return NV12 frames matching the session output; the example reads its width/height/FPS from the environment. The file runs as trusted application code.

The face preset downloads three supported RVC4 Zoo models on first use. A transition image keeps USB populated during initialization. Device internet access is needed for uncached models and build dependencies. Other presets do not load those face models.

## Consumer settings

- Discord: User Settings → Voice & Video → Camera → OAK4 Webcam.
- Google Meet: Settings → Video → Camera → OAK4 Webcam.
- OBS: add a Video Capture Device, select OAK4 Webcam, then MJPEG and the preset's USB resolution at 30 FPS if manual selection is needed.

A host may show a generic composite camera name. Use one consumer at a time.

## Customize

`pipeline.py` dispatches to the selected module in `presets/`. Each module implements `build_pipeline(pipeline)` and returns one NV12 image output matching the mode in `presets/config.py`. The runtime owns pipeline startup/shutdown and MJPEG encoding. Internal branches can do other processing. Re-run the app after editing.

USB descriptors and runtime validation share the preset registry. The transport accepts at most 16,588,800 bytes per encoded frame, while the active USB buffer is `width × height × 2`. Oversized or malformed frames are never truncated.

## Packaging

```bash
oakctl app build . -d DEVICE_IP
oakctl app install ./PACKAGE.oakapp -d DEVICE_IP --enable false
```

Replace `PACKAGE.oakapp` with the generated filename. Installation starts the app and normally stops/disables other apps. The default preset is `face-attention`; change `DEFAULT_PRESET` in `presets/config.py` before packaging if a different default is desired. A distributable package has not yet been validated.

## Lifecycle

The app adds its own `uvc.oakwebcam` function to existing `g1/configs/c.1`. It preserves unrelated functions and restores the original product string and controller binding on normal exit, startup failure and handled stop signals. It refuses to start if another UVC function is linked or its own function already exists. Bounded unbind retries handle transient OS rebinding; a different controller is never displaced.

Each normal run uses a fresh temporary socket directory, avoiding stale sockets after an abrupt exit. The console supervises one camera worker and handles switches and failed-start rollback. Either the console or native bridge exiting stops the app. SIGKILL, power loss or abrupt container teardown cannot perform cleanup. If startup reports a leftover UVC function, inspect and stop its owning process; do not delete unrelated USB state.

## Validation

RGB 1080p: 60 frames captured and decoded at approximately 30 FPS. RGB 4K: negotiated 30 FPS; one host capture delivered about 11 FPS, and the user confirmed it works. LENS XL: user confirmed the colorized view works. Face-attention: user screenshot confirms the overlay in Google Meet. These results do not guarantee throughput in every scene or consumer. See [USB validation](docs/validation-2026-09-10.md), [depth validation](docs/validation-2026-09-10-lens-xl.md), and [face/preset validation](docs/validation-2026-09-10-presets.md).

## Local checks

Use an isolated Python environment with `requirements.txt` installed:

```bash
.venv/bin/python -m unittest discover -s tests -v
bash tests/test-usb-gadget.sh
.venv/bin/cmake --build build --parallel 2
.venv/bin/ctest --test-dir build --output-on-failure
```

If configuring a fresh native build, first run `.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release`. Native and Python transport tests require local Unix sockets; USB tests emulate configfs without touching hardware. No DepthAI source compilation is performed. [Third-party sources and model licenses](THIRD_PARTY.md).
