"""Edit this file to choose the image shown by the USB webcam.

Return exactly one DepthAI output producing 1920x1080 NV12 at 30 FPS.
The runtime owns starting/stopping the pipeline and MJPEG encoding. For custom
processing, convert the resulting image back to this format before returning it.
"""

import depthai as dai


def build_pipeline(pipeline):
    camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    return camera.requestOutput(
        size=(1920, 1080), type=dai.ImgFrame.Type.NV12, fps=30
    )
