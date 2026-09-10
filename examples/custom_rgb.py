"""Minimal custom file: RGB matching the current USB mode.

Select custom in the console and enter /app/examples/custom_rgb.py.
The runtime starts/stops the supplied pipeline and encodes its output.
"""
import os
import depthai as dai


def build_pipeline(pipeline):
    width = int(os.environ.get("OAK_WEBCAM_WIDTH", "3840"))
    height = int(os.environ.get("OAK_WEBCAM_HEIGHT", "2160"))
    fps = int(os.environ.get("OAK_WEBCAM_FPS", "30"))
    camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    return camera.requestOutput(size=(width, height), type=dai.ImgFrame.Type.NV12, fps=fps)
