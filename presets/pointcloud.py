"""NAS metric point cloud with synchronized surface RGB as fixed-view video."""

import depthai as dai

from .nas import build_depth
from .pointcloud_renderer import PointCloudRenderer, View


class RenderPointCloud(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.renderer = PointCloudRenderer(View.from_env())

    def build(self, pointcloud):
        self.link_args(pointcloud)
        # Prefer the latest cloud when rendering is slower than depth generation.
        for name in self.inputs:
            self.inputs[name].setBlocking(False)
            self.inputs[name].setMaxSize(1)
        self.out.setPossibleDatatypes([(dai.DatatypeEnum.ImgFrame, True)])
        return self

    def process(self, message):
        shape = (message.getHeight(), message.getWidth()) if message.isOrganized() else None
        if message.isColor():
            points, colors = message.getPointsRGB()
            image = self.renderer.render(points, shape, colors)
        else:
            image = self.renderer.render(message.getPoints(), shape)
        frame = dai.ImgFrame()
        frame.setCvFrame(image, dai.ImgFrame.Type.BGR888i)
        frame.setTimestamp(message.getTimestamp())
        frame.setTimestampDevice(message.getTimestampDevice())
        frame.setSequenceNum(message.getSequenceNum())
        # A synthetic perspective must not inherit the physical depth intrinsics.
        self.out.send(frame)


def build_pipeline(pipeline, colorized=True):
    depth = build_depth(pipeline)
    cloud = pipeline.create(dai.node.PointCloud)
    cloud.setRunOnHost(True)  # The standalone app's host is the OAK4 CPU.
    cloud.useCPU()
    cloud.initialConfig.setLengthUnit(dai.LengthUnit.METER)
    cloud.initialConfig.setOrganized(True)
    if colorized:
        camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A, sensorFps=30)
        color = camera.requestOutput((1280, 720), type=dai.ImgFrame.Type.RGB888i,
                                     fps=30, enableUndistortion=True)
        align = pipeline.create(dai.node.ImageAlign)
        depth.depth.link(align.input)
        color.link(align.inputAlignTo)
        align.outputAligned.link(cloud.inputDepth)
        color.link(cloud.inputColor)
        cloud.initialConfig.setTargetCoordinateSystem(dai.CameraBoardSocket.CAM_A)
        # PointCloud's internal Sync pairs aligned depth and RGB by timestamp.
        # Retain enough RGB history for neural inference latency (up to 0.5 s).
        cloud.inputColor.setBlocking(False)
        cloud.inputColor.setMaxSize(16)
        cloud.inputDepth.setBlocking(False)
        cloud.inputDepth.setMaxSize(4)
    else:
        cloud.initialConfig.setTargetCoordinateSystem(dai.CameraBoardSocket.CAM_B)
        cloud.inputDepth.setBlocking(False)
        cloud.inputDepth.setMaxSize(1)
        depth.depth.link(cloud.inputDepth)
    render = pipeline.create(RenderPointCloud).build(cloud.outputPointCloud)
    video = pipeline.create(dai.node.ImageManip)
    video.initialConfig.setOutputSize(3840, 2160)
    video.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    video.setMaxOutputFrameSize(3840 * 2160 * 2)
    video.inputImage.setBlocking(False)
    video.inputImage.setMaxSize(1)
    render.out.link(video.inputImage)
    return video.out
