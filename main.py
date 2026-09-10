"""Run the user pipeline and send its single selected output to USB UVC."""

import logging
import os
import signal
import threading

from transport import FrameSender
from presets.config import selected, selected_name

LOG = logging.getLogger(__name__)


def validate_frame(frame, nv12_type, mode=None):
    mode = mode or selected()
    if (frame.getWidth(), frame.getHeight(), frame.getType()) != (mode.width, mode.height, nv12_type):
        raise ValueError(
            f"pipeline.build_pipeline() must output {mode.width}x{mode.height} NV12 frames; "
            f"received {frame.getWidth()}x{frame.getHeight()} {frame.getType()}"
        )


def main():
    import depthai as dai
    from pipeline import build_pipeline

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    mode = selected()
    remote = None
    if os.environ.get("OAK_WEBCAM_INSPECT") == "1":
        remote = dai.RemoteConnection(address="0.0.0.0", webSocketPort=8765, serveFrontend=False)
        LOG.info("Inspection enabled on port 8765; use only on a trusted local network")
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    sender = FrameSender(os.environ.get("OAK_WEBCAM_SOCKET", "/tmp/oak-webcam.sock")).start()
    try:
        with dai.Pipeline() as pipeline:
            output = build_pipeline(pipeline)
            if not isinstance(output, dai.Node.Output):
                raise TypeError("build_pipeline(pipeline) must return one DepthAI Node.Output")
            encoder = pipeline.create(dai.node.VideoEncoder)
            encoder.setDefaultProfilePreset(mode.fps, dai.VideoEncoderProperties.Profile.MJPEG)
            encoder.input.setBlocking(False)
            encoder.input.setMaxSize(1)
            output.link(encoder.input)
            # Validate actual custom output, including changes made after startup.
            raw_queue = output.createOutputQueue(maxSize=1, blocking=False)
            encoded_queue = encoder.out.createOutputQueue(maxSize=1, blocking=False)
            if remote is not None:
                remote.addTopic("webcam", output)
            pipeline.start()
            if remote is not None:
                remote.registerPipeline(pipeline)
            LOG.info("Preset %s: USB mode %sx%s MJPEG at %s FPS", selected_name(), mode.width, mode.height, mode.fps)
            validated = False
            while pipeline.isRunning() and not stop.is_set():
                pipeline.processTasks()
                raw = raw_queue.tryGet()
                if raw is not None:
                    validate_frame(raw, dai.ImgFrame.Type.NV12, mode)
                    validated = True
                frame = encoded_queue.tryGet()
                if frame is not None and validated:
                    sender.submit(bytes(frame.getData()))
                stop.wait(0.002)
    finally:
        sender.close()


if __name__ == "__main__":
    main()
