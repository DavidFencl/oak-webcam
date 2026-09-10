# LENS XL webcam validation

Device: OAK4-D R7 serial 1259426771, Luxonis OS 1.40.0. SDK 3.10.0, depthai-nodes 0.6.1. Standalone app, Fedora USB consumer.

Selected built-in NEURAL_DEPTH_EXTRA_LARGE (1248×780). CAM_B/C use the reference 10 FPS setting; expected new depth rate is approximately 9 FPS. Colorized disparity is letterboxed into 3840×2160 NV12 for the existing 30 FPS MJPEG UVC mode.

Local Python checks and six transport tests pass; ARM64 development build passes. The initial 9 FPS camera configuration encountered a camera SDK crash. With the reference 10 FPS setting the colormap received frames, revealing an ImageManip allocation error: GPU-padded NV12 required 12,533,760 bytes versus the tightly packed 12,441,600-byte allocation. The allocation now allows 16,588,800 bytes.

The corrected app starts and negotiates 3840×2160 MJPEG at 30 FPS with the host consumer. Final logs are in evidence/2026-09-10-lens-xl/running.log; the allocation error is in startup.log. These logs alone do not prove correct visual output. FFmpeg verification was blocked by an existing consumer holding /dev/video0 (Device or resource busy); decoded output verification is pending closing that preview. Holistic replay remains pending for this standalone USB topology.

No firmware update, reset, flash or publication was performed.

User subsequently confirmed the colorized depth view works and requested no further investigation. Independent capture remains unperformed because the consumer was using the webcam.
