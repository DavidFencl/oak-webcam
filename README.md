# OAK4 Webcam

Use your OAK4 D Pro as a USB webcam in Google Meet, Discord, or OBS. A browser console lets you switch between RGB video, depth, point clouds, face overlays, and your own Python pipeline. Processing runs on the OAK; the computer receives a normal MJPEG USB camera.

## What you need

- An OAK4 D Pro with adequate power and a USB **data** connection to your computer.
- [Git](https://git-scm.com/downloads) and [Luxonis oakctl](https://docs.luxonis.com/software-v3/oak-apps/oakctl/#installation) installed on the computer. Local Python setup is only needed for development/tests.
- A network connection from your computer to the OAK. Ethernet is recommended for management: starting/stopping this app briefly reconnects the USB composite device.
- Internet access on the OAK for the first build and uncached models. See Luxonis' [USB internet sharing instructions](https://docs.luxonis.com/software-v3/oak-apps/oakctl/#usb-internet-sharing) if needed.

This project targets OAK4 and DepthAI v3. Keep only one app in control of the device's cameras.

## First run

Clone the repository, including its native USB bridge dependency:

```bash
git clone --recurse-submodules https://github.com/DavidFencl/oak-webcam.git
cd oak-webcam
oakctl device list
```

Replace `DEVICE_IP` below with the device address or serial from discovery. Check existing apps and stop whichever app currently owns the cameras using `oakctl app stop APP_ID -d DEVICE_IP`.

```bash
oakctl app list -d DEVICE_IP
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=rgb-4k
```

The first build can take several minutes. `--detach` returns before the camera is ready. Check startup and find the browser console:

```bash
oakctl app list -d DEVICE_IP
oakctl app logs 00000000-0000-0000-0000-000000000000 -d DEVICE_IP --no-follow --tail 2000
```

1. Open the **frontend URL** shown by `oakctl app list`. Luxonis assigns its port; do not assume port 8080.
2. In the logs, find `Webcam console: .../#token=...`. Copy the value after `#token=` into the console's **Console token** field and press **Connect**. Alternatively, append that fragment to the frontend URL before opening it. Treat the token as a password; a new app launch generates a new one by default.
3. Wait for **Running** and a moving preview with fresh frame counts. Select **OAK4 Webcam** in your video application's camera settings. Some hosts show a generic composite-camera name.

The all-zero app ID above belongs to `oakctl app run` development sessions. Installed packages have their own IDs, shown by `oakctl app list`.

For Discord, use **User Settings → Voice & Video → Camera**. For Google Meet, use **Settings → Video → Camera**. In OBS, add a **Video Capture Device**; select MJPEG and the session's USB resolution if manual configuration is needed. Use one USB camera consumer at a time; the browser console can remain open alongside it.

## Choose a pipeline

Select a pipeline in the console and press **Switch pipeline**. For point clouds, the button is **Apply pipeline and fixed view**. A transition screen appears during initialization. Failed changes attempt to restore the previous pipeline, with the error displayed in the console.

| Preset | What you see |
| --- | --- |
| Build finishes but `App output:` stays empty | In another terminal, run `oakctl app list -d DEVICE_IP`. If the app is `ready`, start the existing build with `oakctl app start APP_ID -d DEVICE_IP`, then inspect logs. A device reboot during development startup has produced this state; rebuilding is unnecessary. If already running, inspect logs instead of starting another camera process. |
| `rgb-1080p` | RGB at 1920 × 1080, requesting 30 FPS |
| `rgb-4k` | Native RGB at 3840 × 2160, requesting 30 FPS |
| `lens-xl` | Highest visual-quality LENS XL depth option: 1248 × 780, about 9 new frames/s |
| `nas` | Colorized Neural Assisted Stereo depth, requesting 30 FPS |
| `pointcloud` | RGB-colored metric point cloud rendered from a fixed virtual camera |
| `pointcloud-depth` | The same point-cloud geometry, colored by depth |
| `face-attention` | Expression candidate/confidence, head direction and facing-camera streak; these do not measure mood or attention span |
| `custom` | A trusted Python pipeline file you supply |

The initial preset sets the session's USB mode: `rgb-1080p` starts 1080p/30; the others start 4K/30. Later prepared presets are resized to that mode so switching keeps USB connected. Custom files must output the session dimensions. Restart the app to change the USB mode itself.

The quickstart explicitly selects `rgb-4k`; without an override, the repository default is `face-attention`. Advertised USB FPS is not a guarantee of fresh-frame throughput. Model speed and bandwidth matter; one 4K host capture delivered about 11 FPS. Upscaling does not add detail. See [preset details](docs/presets.md).

## Set a point-cloud viewpoint

Choose `pointcloud` or `pointcloud-depth`. **Angled view** fills in the default virtual camera settings; **Front view** reproduces the physical camera viewpoint. Adjust yaw, pitch, orbit distance, look-at depth, and field of view, then press **Apply pipeline and fixed view**.

The resulting view stays fixed in the outgoing 2D video. Angled views reveal depth but can also expose holes where the physical camera could not see a surface. See [point-cloud settings](docs/pointcloud.md) and the [console API](docs/control-panel.md).

## Use your own Python file

Start with [examples/custom_rgb.py](examples/custom_rgb.py). Place your file in this repository and run the app again to copy it onto the OAK. For example, local `examples/mine.py` becomes `/app/examples/mine.py`.

Choose **custom** in the console, enter that **OAK-side absolute path**, and press **Switch pipeline**. The file must define `build_pipeline(pipeline)` and return one DepthAI output emitting NV12 frames at `OAK_WEBCAM_WIDTH` × `OAK_WEBCAM_HEIGHT`. The runtime starts/stops the pipeline and encodes its frames; the example reads the required dimensions from the environment.

Custom files execute with the app's permissions, so use code you trust. The console accepts existing device files, not uploads or URLs. See the [custom pipeline contract](docs/control-panel.md#load-your-own-python-pipeline).

## Stop, restart, or change startup settings

Use the app ID from `oakctl app list`:

```bash
oakctl app stop APP_ID -d DEVICE_IP
oakctl app start APP_ID -d DEVICE_IP --env OAK_WEBCAM_PRESET=rgb-1080p
```

To rebuild after source changes, stop the app and run `oakctl app run .` again. A full app restart can change the frontend port and token; check the listing and logs again. Reopen the camera in your video application after USB reconnects.

Google Meet mirrors its local preview. By default, overlay text is correct for recipients and the unmirrored console preview. To make face and transition text readable in a mirrored self-view, add `--env OAK_WEBCAM_MIRROR_TEXT=1` when starting the app. This preflips the text, so recipients see reversed text. It does not flip the camera image.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| No frontend link, or the console will not open | Wait for startup, rerun `oakctl app list`, and use its current frontend URL. Check logs for the listening port and startup errors. Older builds without frontend registration need rebuilding from this version. |
| Console asks for a token | Read the latest `Webcam console` log line. Tokens change on app restart unless `OAK_WEBCAM_CONTROL_TOKEN` is configured. |
| Webcam missing from the host | Check USB data/power, app logs, and camera ownership. Starting the app briefly reconnects USB; reopen the consumer's camera selector. |
| Starting/switching screen stays visible | Check the console error and frame age, plus app logs. First-use model downloads require internet. A running process alone does not prove video is flowing. |
| Camera is busy | Close the other USB consumer, or stop the other OAK app that owns the cameras. The browser console uses its own preview and does not claim the host USB camera. |
| Point-cloud image looks flat or has holes | Try **Angled view**, then apply. Missing surfaces cannot be reconstructed from a single camera viewpoint. |
| Custom file fails | Use an absolute path on the OAK, a callable `build_pipeline`, and the required NV12 dimensions. Review logs for the Python exception. |
| Native dependency is missing after cloning | Run `git submodule update --init --recursive` in the repository. |

Use the HTTP console on a trusted local network. The token protects control requests but HTTP does not encrypt them.

## Development and packaging

`presets/config.py` lists prepared pipelines; `pipeline.py` dispatches them or loads a custom file. `control_panel.py` supervises one camera worker, `main.py` encodes its output, and the native bridge serves USB video. The app adds its own UVC function and preserves unrelated USB functions. Normal shutdown restores the gadget; abrupt power loss cannot run cleanup.

Build a reusable package with `oakctl app build . -d DEVICE_IP`, then install the generated file:

```bash
oakctl app install PACKAGE.oakapp -d DEVICE_IP --enable false --env OAK_WEBCAM_PRESET=rgb-4k
```

Installation starts the app by default and normally stops/disables other apps. `--enable false` disables boot autostart. Source deployment is the validated path; a distributable package has not been separately validated.

For local development, create an isolated environment and install `requirements.txt` plus CMake. With the environment at `.venv`:

```bash
.venv/bin/python -m unittest discover -s tests -v
bash tests/test-usb-gadget.sh
.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
.venv/bin/cmake --build build --parallel 2
.venv/bin/ctest --test-dir build --output-on-failure
```

Native builds also need a C/C++ compiler and pkg-config. Python/native transport tests use local sockets; gadget tests emulate configfs without touching hardware. DepthAI uses prebuilt SDK packages, not a source build.

[Console documentation](docs/control-panel.md) · [Validation notes](docs/validation-2026-09-10-live-console.md) · [Third-party licenses](THIRD_PARTY.md)
