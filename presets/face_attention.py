"""Single-person facial-expression and head-direction webcam overlay."""
import cv2
import os
import json
import depthai as dai
from depthai_nodes.node import FrameCropper, GatherData, ParsingNeuralNetwork

from .attention_state import FacingTimer
from .models import archives
from .overlay_panel import draw_panel

INPUT_FPS = 20


class SingleFace(dai.node.HostNode):
    """Send no crops when more than one face is visible."""
    def build(self, detections):
        self.link_args(detections)
        self.out.setPossibleDatatypes([(dai.DatatypeEnum.ImgDetections, True)])
        return self

    def process(self, detections):
        selected = dai.ImgDetections()
        selected.setTimestamp(detections.getTimestamp())
        selected.setTimestampDevice(detections.getTimestampDevice())
        selected.setSequenceNum(detections.getSequenceNum())
        selected.setTransformation(detections.getTransformation())
        selected.detections = detections.detections if len(detections.detections) == 1 else []
        self.out.send(selected)


class FaceOverlay(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.timer = FacingTimer()
        self.mirror_text = os.environ.get("OAK_WEBCAM_MIRROR_TEXT") == "1"

    def build(self, image, detections, expressions, poses):
        self.link_args(image, detections, expressions, poses)
        self.out.setPossibleDatatypes([(dai.DatatypeEnum.ImgFrame, True)])
        return self

    def process(self, frame, detections, expressions, poses):
        image = frame.getCvFrame().copy()
        count = len(detections.detections)
        timestamp = frame.getTimestamp().total_seconds()
        lines = ["Expression + head direction", "No face detected"]
        if count == 1 and len(expressions.items) == 1 and len(poses.items) == 1:
            det = detections.detections[0]
            box = tuple(det.getBoundingBox().getOuterRect())
            expression = expressions.items[0]
            pose = poses.items[0]
            # Model head ordering verified against the Luxonis reference example.
            yaw, roll, pitch = (float(pose[key].prediction) for key in ("0", "1", "2"))
            facing, duration = self.timer.update(timestamp, yaw, pitch, box)
            score = float(expression.top_score)
            label = str(expression.top_class)
            confidence = "; low confidence" if score < 0.5 else ""
            lines = [
                f"Expression candidate: {label} (score {score:.2f}{confidence})",
                f"Head: {'facing camera' if facing else 'turned away'} | Facing streak: {duration:.1f}s",
                f"Yaw {yaw:+.0f}   Pitch {pitch:+.0f}   Roll {roll:+.0f} deg",
            ]
            height, width = image.shape[:2]
            x1, y1, x2, y2 = box
            cv2.rectangle(image, (int(x1 * width), int(y1 * height)),
                          (int(x2 * width), int(y2 * height)), (80, 220, 80), 2)
        else:
            self.timer.update(timestamp)
            if count > 1:
                lines[1] = "Multiple faces: use one-person view"
            elif count == 1:
                lines[1] = "Waiting for face estimates"
        lines.append("Visible cues only; not a measure of mood or attention span")
        draw_panel(image, lines, self.mirror_text)
        result = dai.ImgFrame()
        result.setCvFrame(image, dai.ImgFrame.Type.BGR888i)
        result.setTimestamp(frame.getTimestamp())
        result.setTimestampDevice(frame.getTimestampDevice())
        result.setSequenceNum(frame.getSequenceNum())
        result.setTransformation(frame.getTransformation())
        self.out.send(result)


def build_pipeline(pipeline):
    models = archives()
    camera = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    image = camera.requestOutput((1280, 720), type=dai.ImgFrame.Type.BGR888i, fps=INPUT_FPS)
    resize = pipeline.create(dai.node.ImageManip)
    resize.initialConfig.setOutputSize(*models["face"].getInputSize())
    resize.setMaxOutputFrameSize(640 * 384 * 3)
    image.link(resize.inputImage)
    detector = pipeline.create(ParsingNeuralNetwork).build(resize.out, models["face"])
    detector.input.setBlocking(True)
    selected = pipeline.create(SingleFace).build(detector.out)

    gathered = {}
    for name in ("expression", "pose"):
        crop = pipeline.create(FrameCropper).fromImgDetections(
            inputImgDetections=selected.out, outputSize=models[name].getInputSize()
        ).build(inputImage=image)
        network = pipeline.create(ParsingNeuralNetwork).build(crop.out, models[name])
        if name == "expression" and os.environ.get("OAK_WEBCAM_EXPRESSION_DIAGNOSTICS") == "1":
            parser = network.getParser()
            original_extract = parser.extract
            remaining = [5]

            def extract_with_diagnostics(message):
                scores = original_extract(message)
                if remaining[0] > 0:
                    print("EXPRESSION_RAW " + json.dumps({
                        "values": scores.tolist(), "sum": float(scores.sum()),
                        "min": float(scores.min()), "max": float(scores.max()),
                        "parser_is_softmax": parser.is_softmax,
                    }), flush=True)
                    remaining[0] -= 1
                return scores

            parser.extract = extract_with_diagnostics
        network.input.setBlocking(True)
        output = network.outputs if name == "pose" else network.out
        gathered[name] = pipeline.create(GatherData).build(
            cameraFps=INPUT_FPS, inputData=output, inputReference=selected.out
        )
    overlay = pipeline.create(FaceOverlay).build(
        image, detector.out, gathered["expression"].out, gathered["pose"].out
    )
    video = pipeline.create(dai.node.ImageManip)
    video.initialConfig.setOutputSize(3840, 2160)
    video.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    video.setMaxOutputFrameSize(3840 * 2160 * 2)
    video.inputImage.setBlocking(False)
    video.inputImage.setMaxSize(1)
    overlay.out.link(video.inputImage)
    return video.out
