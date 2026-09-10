# Project Brief: OAK4 webcam

## Goal
Let the user define a DepthAI pipeline with one video output and select it as a camera in Discord, Google Meet, or OBS.

## Device
OAK4 D Pro.

## Where it should run
Processing runs on the OAK4 as a standalone OAK App. Consumer applications run on the user's computer.

## Scene
User-selected camera scene; no recognition target specified.

## Targets / events
Continuous video, including custom pipeline processing.

## Outputs / actions
One selectable webcam video source.

## Success
The computer enumerates the camera and receives moving frames from the selected pipeline output. Each named consumer can display that output in a separate session.

## Constraints
DepthAI v3. Keep custom pipeline definition separate from webcam plumbing. Hardware and application compatibility require real-device validation.

## Now / later
First demo: one fixed video mode and a default RGB pipeline with an explicit customization point. Later: additional modes, camera controls, audio, graphical pipeline editing, simultaneous consumers.

## Assumptions and open questions
User confirmed USB UVC and Python pipeline definition. Host OS, device availability and firmware compatibility are unverified.
