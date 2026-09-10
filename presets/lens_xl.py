"""Edit this file to choose the image shown by the USB webcam.

Return exactly one DepthAI output producing 3840x2160 NV12.
LENS XL produces about 9 fresh depth frames/s; USB remains a 30 FPS video mode.
The runtime owns starting/stopping the pipeline and MJPEG encoding. For custom
processing, convert the resulting image back to this format before returning it.
"""

import depthai as dai
from depthai_nodes.node import ApplyDepthColormap


def build_pipeline(pipeline):
    left = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_B, sensorFps=10
    )
    right = pipeline.create(dai.node.Camera).build(
        dai.CameraBoardSocket.CAM_C, sensorFps=10
    )
    depth = pipeline.create(dai.node.NeuralDepth).build(
        left.requestFullResolutionOutput(),
        right.requestFullResolutionOutput(),
        dai.DeviceModelZoo.NEURAL_DEPTH_EXTRA_LARGE,
    )
    # Larger disparity is nearer: JET shows near surfaces red and far ones blue.
    # Invalid pixels are black; percentile normalization adapts to the scene.
    color = pipeline.create(ApplyDepthColormap).build(depth.disparity)
    color.setPercentileRange(low=2, high=98)
    video = pipeline.create(dai.node.ImageManip)
    video.initialConfig.setOutputSize(
        3840, 2160, dai.ImageManipConfig.ResizeMode.LETTERBOX
    )
    video.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    # Leave room for GPU NV12 plane/row alignment (12,533,760 bytes observed).
    video.setMaxOutputFrameSize(3840 * 2160 * 2)
    video.inputImage.setBlocking(False)
    video.inputImage.setMaxSize(1)
    color.out.link(video.inputImage)
    return video.out
