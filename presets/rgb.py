"""Original RGB webcam, in the selected native resolution."""
import depthai as dai
from .config import selected


def build_pipeline(pipeline):
    mode = selected()
    camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    return camera.requestOutput(
        size=(mode.width, mode.height), type=dai.ImgFrame.Type.NV12, fps=mode.fps
    )
