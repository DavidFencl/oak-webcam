# USB startup repair validation

Target: USB OAK4-D R7, serial 1259426771, Luxonis OS 1.40.0. Fedora host.

Original `oakctl app run .` failure reproduced once: immediate UDC read still showed the original controller after an unbind request. Bounded retries with two settling reads resolve this on the real device. Exact external rebinding actor is not established.

Next dependent checks exposed two additional defects, both repaired:
- configfs relative symlink targets require the caller to be in the link's parent directory.
- Installed native bridge requires a relative runtime search path for the installed UVC shared library.

Verification:
- Six shell lifecycle scenarios pass, including transient/persistent rebinding and changed ownership. The filesystem simulation now checks configfs target resolution.
- Native build and relocated install pass; installed executable runs without LD_LIBRARY_PATH.
- Device development build and pipeline startup pass.
- Fedora advertises MJPEG 1920x1080 on /dev/video0.
- FFmpeg captures 60 frames in about two seconds; all decode without errors. ffprobe confirms 60 frames, MJPEG, 1920x1080. A representative image was opened and inspected.
- Evidence: evidence/2026-09-10-usb-fix/capture.mjpeg and frame.png.
- Stopping the app removes uvc.oakwebcam and preserves all five original config links, with a600000.dwc3 rebound; ADB remains available.

No RemoteConnection endpoint is instrumented; the observed external UVC output is the evidence. Holistic replay, prolonged streaming, custom rendering and Discord/Meet/OBS UI checks remain pending.
