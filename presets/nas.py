"""Neural Assisted Stereo disparity visualization for the USB webcam."""

import depthai as dai
from depthai_nodes.node import ApplyDepthColormap


def build_depth(pipeline, fps=30):
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B, sensorFps=fps)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C, sensorFps=fps)
    return pipeline.create(dai.node.NeuralAssistedStereo).build(
        left.requestFullResolutionOutput(), right.requestFullResolutionOutput()
    )


def build_pipeline(pipeline):
    depth = build_depth(pipeline)
    color = pipeline.create(ApplyDepthColormap).build(depth.disparity)
    color.setPercentileRange(low=2, high=98)
    video = pipeline.create(dai.node.ImageManip)
    video.initialConfig.setOutputSize(3840, 2160, dai.ImageManipConfig.ResizeMode.LETTERBOX)
    video.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    video.setMaxOutputFrameSize(3840 * 2160 * 2)
    video.inputImage.setBlocking(False)
    video.inputImage.setMaxSize(1)
    color.out.link(video.inputImage)
    return video.out
