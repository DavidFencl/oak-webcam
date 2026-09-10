# OAK setup notes

Live observations on 2026-09-10; recheck before deployment.

## Latest validation (supersedes initial blockers below)

Development app now builds and runs on serial 1259426771. USB startup repairs and Fedora capture/decode of 60 MJPEG 1920x1080 frames at approximately 30 FPS are recorded in [validation-2026-09-10.md](validation-2026-09-10.md). Graceful stop removes the app UVC function and restores the original five USB links/controller. Earlier DNS/clock build failure is no longer blocking this development run. No firmware or persistent device setting was changed during this repair.

## Host

- Fedora Linux x86_64, kernel 7.1.13-200.fc44.x86_64.
- oakctl 0.29.1; Python 3.14.7.
- Project .venv imports DepthAI 3.10.0 through system-site-packages; CMake installed locally in .venv.
- Sandbox blocks mDNS and Unix socket binding; approved external checks were used.

## Device

- One USB OAK4 detected: model reported as OAK4-D R7, serial 1259426771, ADB ID 4b1153d3.
- Luxonis OS 1.40.0, oak-agent 0.26.0, ARM64; not adopted to Hub.
- oakctl device info and app list succeeded; app list was empty.
- USB g1/c.1 binds diagnostic/ADB/gate/device/NCM functions. Factory uvc.0 exists but is not linked; preserve it.
- UDC a600000.dwc3. No host /dev/video devices before app deployment.
- No default route or external DNS servers reported. Base image download failed DNS resolution. Device clock reports January 1970.
- oakctl usbd status reports disabled.
- /data has approximately 73 GB free; root filesystem has approximately 624 MB free.
- No command has yet proved live frames for this app.

## Open setup issues

`oakctl app build /home/davidfencl/Documents/Work/oak-webcam -d 1259426771` reached the device, then failed downloading luxonis/oakapp-base:1.2.5 with incorrect system date and DNS failure. No .oakapp package was produced.

Next action: provide device internet and time synchronization (e.g. authorized oakctl USB internet sharing or an internet-connected Ethernet link), then retry that build. USB consumer verification is pending. Device is reachable, not yet proven as a webcam. No firmware, network or Hub configuration changed.

An approved `oakctl usbd enable` attempt failed because sudo requires an interactive password. Status remains disabled. Run that command in the user's interactive terminal; no password should be passed through chat or command arguments.
