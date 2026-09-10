# Prepared presets

The registry is `presets/config.py`; `pipeline.py` imports its selected implementation. Set the initial `OAK_WEBCAM_PRESET` through `oakctl app run --env`. That choice sets USB descriptors. Use the [browser console](control-panel.md) for later switches while preserving the session's USB format; outputs are resized to that format. Unknown initial names fail before changing USB state.

## Switch commands

From the repository root, after stopping the currently running camera app:

```bash
# Original webcam
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=rgb-1080p

# Native 4K RGB
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=rgb-4k

# Highest visual-quality LENS model tried
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=lens-xl

# Neural Assisted Stereo
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=nas

# Facial-expression / head-direction demo (also the default)
oakctl app run . -d DEVICE_IP --detach --env OAK_WEBCAM_PRESET=face-attention
```

Run **one** of those commands per session. Before switching:

```bash
oakctl app stop 00000000-0000-0000-0000-000000000000 -d DEVICE_IP
```

Reopen the consumer's camera preview afterward. List available presets locally without DepthAI or a camera:

```bash
.venv/bin/python -m presets.config
```

## RGB

`rgb-1080p` and `rgb-4k` use `presets/rgb.py`: CAM_A NV12 at 1920×1080 or 3840×2160, requested at 30 FPS. They preserve the two original modes. 4K delivery depends on MJPEG size, USB link and consumer; negotiating 30 FPS does not prove 30 unique frames/s.

## LENS XL

`presets/lens_xl.py` uses CAM_B/C and `NEURAL_DEPTH_EXTRA_LARGE` (1248×780). Sensors run at the reference 10 FPS; Luxonis benchmarks XL around 9.4 FPS. The colormap is letterboxed to 4K NV12, with allocation headroom for GPU row padding.

Near surfaces have larger disparity and appear red; far surfaces appear blue. Invalid depth is black. The 2nd–98th percentile normalization adapts to each scene: colors are **not a fixed metric distance scale**. 4K is an upscaled visualization, not native 4K depth. The user confirmed this preset works.

[Luxonis depth comparison and benchmarks](https://docs.luxonis.com/overview/toplevel-features/depth.md).

## Neural Assisted Stereo (NAS)

`nas` combines neural depth, a virtual projection pattern and stereo matching using the DepthAI v3 [NeuralAssistedStereo node](https://docs.luxonis.com/software-v3/depthai/depthai-components/nodes/neural_assisted_stereo.md). CAM_B/C request full-resolution images at 30 FPS. The disparity colormap uses the same scene-adaptive near-red/far-blue mapping as LENS XL, letterboxed into 4K video. Neither the visualization resolution nor the USB 30 FPS mode proves native 4K depth or 30 unique frames per second. A live encoded 3840×2160 output frame was decoded and inspected on 2026-09-10 (`evidence/2026-09-10-nas/sample.jpg`); consumer throughput was not measured.

## Point cloud

`pointcloud` renders NAS metric XYZ points with synchronized RGB surface colors. `pointcloud-depth` renders the same kind of geometry using distance colors. Both default to a fixed physical-camera pose. See [point-cloud view settings](pointcloud.md). The source render is 1280×720, upscaled to 4K by default.

## Custom Python file

Select `custom` with a file path in the [console](control-panel.md), or start with `--env OAK_WEBCAM_PRESET=custom --env OAK_WEBCAM_CUSTOM_PIPELINE=/app/examples/custom_rgb.py`. The path refers to the OAK app filesystem. Files in the repository are copied into `/app` during deployment. The module must export `build_pipeline(pipeline)` and return one NV12 image output matching the session USB dimensions; custom code is responsible for that contract. The runtime owns pipeline start/stop and MJPEG encoding. Failed loading or startup reports an error and attempts to restore the previous running preset.

## Facial expression and head direction

`presets/face_attention.py` runs these on-device models:

| Stage | Zoo variant | Purpose |
| --- | --- | --- |
| Detection | `luxonis/yunet:640x360` | Locate the visible face |
| Expression | `luxonis/emotion-recognition:260x260` | Classify facial appearance into one of eight expression categories |
| Head pose | `luxonis/head-pose-estimation:60x60` | Estimate yaw, roll and pitch |

RGB input is 1280×720 at 20 FPS; the annotated image is scaled to 3840×2160 NV12 for USB. Models are downloaded before the gadget starts so download time cannot exhaust the bridge's first-frame timeout. Named Zoo variants are recorded in `presets/models.py`; they are not immutable weight revisions. Licenses and upstream sources are in `THIRD_PARTY.md`.

The overlay displays:

- **Expression candidate and score:** neutral, happiness, sadness, surprise, fear, disgust, anger or contempt. The leading candidate remains visible; below score 0.5 it is explicitly marked `low confidence`. The score is a model output, not a calibrated probability of a person's feelings. This display does not make a weak prediction more reliable.
- **Head direction:** `facing camera` when absolute yaw and pitch are each at most 20 degrees; otherwise `turned away`. This is not eye tracking or proof of attention to the screen.
- **Facing-camera streak:** elapsed time satisfying that geometric condition. Resets on turning away, no face, multiple faces, a large face-position jump, or a frame gap over 0.5 seconds. It measures neither attention span nor cognitive performance.

Use a single visible face with adequate lighting. It does not identify you or distinguish you from another person replacing you at the same position. More than one detected face suspends estimates. No per-person history is persisted. Internal mood, distraction and mental-health conditions cannot be reliably determined from this pipeline.

## Mirrored previews

Google Meet mirrors your own camera preview, including text rendered into the video. The pipeline does not horizontally flip frames. [Google documents this self-view behavior](https://support.google.com/meet/answer/10058482). A mirrored self-preview does not mean the outgoing video is mirrored; check from another participant or a non-mirrored capture before changing camera orientation. Flipping the whole outgoing frame to correct only the local preview reverses it for recipients.

## Optional inspection

For debugging on a **trusted local network**, add `--env OAK_WEBCAM_INSPECT=1` to the run command. This enables an unauthenticated local WebSocket on device port 8765; it is off by default. The `webcam` topic contains the final NV12 pipeline output.

Installed oakctl 0.29.1 cannot decode this padded NV12 encoding with `inspect frames`. Its raw protobuf output can be requested with `inspect dump webcam --count 1`, but local NV12 decoding was not completed in this session. Use the consumer preview for a visual check, or FFmpeg on the host USB device after closing other consumers. Inspection alone does not prove USB delivery.

Re-run without the inspection environment variable to disable it. No cloud video relay is added.

### Readable text in your mirrored self-preview

The face overlay uses a compact panel inside the lower central area to reduce clipping by consumer framing. Add `--env OAK_WEBCAM_MIRROR_TEXT=1` when running `face-attention` to pre-mirror **only the text panel**, so it reads normally in Meet's mirrored self-preview. Camera imagery and detection geometry remain unchanged. Other participants and unmirrored recordings will see reversed text with this option; use `--env OAK_WEBCAM_MIRROR_TEXT=0` for normal outgoing text (the default).
