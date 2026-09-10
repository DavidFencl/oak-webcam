# Third-party sources

USB integration is adapted from Luxonis oak-examples/cpp/uvc (MIT).
Reference: https://github.com/luxonis/oak-examples/tree/main/cpp/uvc

vendor/uvc-gadget is https://github.com/luxonis/uvc-gadget at commit
860b0b506bf2e17662458d5c642eaba5bfc07831, the submodule revision pinned by
the local oak-examples reference. Retain its COPYING, LICENSE and per-file notices.
The native bridge uses this library; it does not compile DepthAI from source.

## Face preset models

Resolved through the Luxonis Model Zoo for RVC4; exact variants are declared in presets/models.py. No model training or conversion is performed. Zoo variants are named references, not immutable weight hashes.

- luxonis/yunet:640x360 — MIT, Wei Wu et al. / OpenCV Zoo. https://models.luxonis.com/luxonis/yunet and https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- luxonis/emotion-recognition:260x260 — Apache 2.0, A. Savchenko. https://models.luxonis.com/luxonis/emotion-recognition and https://github.com/av-savchenko/face-emotion-recognition
- luxonis/head-pose-estimation:60x60 — Apache 2.0, OpenVINO / PINTO model zoo. https://models.luxonis.com/luxonis/head-pose-estimation and https://github.com/openvinotoolkit/open_model_zoo/tree/master/models/intel/head-pose-estimation-adas-0001

The pipeline wiring follows Luxonis oak-examples face-detection/emotion-recognition and head-posture-detection (MIT). depthai-nodes 0.6.1 provides parsing, synchronized crops, gathering and depth visualization.
