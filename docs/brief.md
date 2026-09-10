# Project Brief: OAK4 webcam

## Goal
Let the user define a DepthAI pipeline with one video output and select it as a camera in Discord, Google Meet, or OBS.

## Device
OAK4 D Pro.

## Where it should run
Processing runs on the OAK4 as a standalone OAK App. Consumer applications run on the user's computer.

## Scene
User-selected scene; optional single-person facial expression and head-direction visualization.

## Targets / events
Continuous video, including custom pipeline processing and visible face cues.

## Outputs / actions
One selectable webcam video source.

## Success
The computer enumerates the camera and receives moving frames from the selected pipeline output. Each named consumer can display that output in a separate session.

## Constraints
DepthAI v3. Keep custom pipeline definition separate from webcam plumbing. Hardware and application compatibility require real-device validation.

## Now / later
Prepared RGB 1080p, RGB 4K, LENS XL, Neural Assisted Stereo and face-expression/head-direction presets. Add a fixed-view point-cloud visualization as ordinary webcam video and a browser console for changing pipelines while keeping the webcam connected. Mood and attention span are not measurable from visible cues. Later: audio, arbitrary graphical pipeline editing and simultaneous consumers.

## Assumptions and open questions
User confirmed USB UVC and Python pipeline definition. Host OS, device availability and firmware compatibility are unverified.
