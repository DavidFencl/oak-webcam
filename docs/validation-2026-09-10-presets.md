# Prepared preset and face-overlay validation

Date: 2026-09-10. Device: OAK4-D R7 serial 1259426771, Luxonis OS 1.40.0. SDK 3.10.0, depthai-nodes 0.6.1. Standalone OAK App; Fedora host and Google Meet consumer.

## Verified

- Ten Python tests pass: transport, preset-dependent dimensions, unknown-preset rejection, timer resets for missing/away/stale frames and geometric face jumps.
- Eight shell scenarios pass: both USB resolutions, invalid mode before mutation, cleanup, active-UVC conflict, partial failure and controller rebinding/ownership.
- ARM64 app builds with prebuilt DepthAI. YuNet 640×360, Emotion Recognition 260×260, Head Pose Estimation 60×60 resolve for RVC4.
- The face-attention preset starts; host negotiates 3840×2160 MJPEG at 30 FPS.
- User screenshot (evidence/2026-09-10-face-attention/google-meet.png) of Google Meet shows the live RGB image, a detected face rectangle, expression estimate with score, head-direction output, angles and facing-camera streak. The self-preview is mirrored, including text; no frame flip is performed by the pipeline. This confirms the inference/overlay path reaches the consumer, not the correctness of inferred internal mood or attention.
- LENS XL had already been confirmed working by the user, who requested no further investigation of it.

## Startup observations

Device uptime showed a restart during initial model preparation; the cause is not established. A leftover socket subsequently prevented bridge binding. Normal startup now creates a unique temporary socket directory and cleans up only that directory. The new preset then ran successfully. Model downloads occur before USB mutation and before the first-frame timeout.

## Limits

Face/no-face and multiple-face timer behavior is covered by logic and local checks; live branch coverage and quantitative model accuracy were not established. No clinical or cognitive measurement is claimed. The 20 FPS source and 30 FPS USB mode are requested settings, not measured end-to-end throughput.

The optional inspection endpoint exposed padded NV12, which oakctl 0.29.1 cannot decode with inspect frames. A raw dump was interrupted; the user-provided Meet screenshot supplies final-output evidence instead. Logs are in evidence/2026-09-10-face-attention/. Holistic replay, other consumer apps and a distributable package remain pending. No firmware update, reset, flash or publication was performed by the agent.

## Overlay follow-up

The user's second Meet screenshot showed consumer cropping at the top and mirrored text. The overlay is now a measured-width compact panel in the lower central 60% of the image, with generous outer margins. OAK_WEBCAM_MIRROR_TEXT=1 flips only the panel for readable mirrored self-preview; outgoing text is reversed in that mode. The default remains 0 for normal recipients. A simulated 1280×720 preview was opened and checked at evidence/2026-09-10-overlay/meet-preview.png; normal and mirrored-panel images matched exactly after the consumer mirror transform. Actual consumer framing can still crop content under sufficiently aggressive auto-framing.
