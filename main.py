"""Run the user pipeline and send its single selected output to USB UVC."""

import logging
import os
import signal
import threading

from transport import FrameSender

LOG = logging.getLogger(__name__)


def validate_frame(frame, nv12_type):
    if (frame.getWidth(), frame.getHeight(), frame.getType()) != (1920, 1080, nv12_type):
        raise ValueError(
            "pipeline.build_pipeline() must output 1920x1080 NV12 frames at 30 FPS; "
            f"received {frame.getWidth()}x{frame.getHeight()} {frame.getType()}"
        )


def main():
    import depthai as dai
    from pipeline import build_pipeline

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
            encoder.setDefaultProfilePreset(30, dai.VideoEncoderProperties.Profile.MJPEG)
            encoder.input.setBlocking(False)
            encoder.input.setMaxSize(1)
            output.link(encoder.input)
            # Validate actual custom output, including changes made after startup.
            raw_queue = output.createOutputQueue(maxSize=1, blocking=False)
            encoded_queue = encoder.out.createOutputQueue(maxSize=1, blocking=False)
            pipeline.start()
            LOG.info("Pipeline started: USB webcam mode is 1920x1080 MJPEG at 30 FPS")
            validated = False
            while pipeline.isRunning() and not stop.is_set():
                pipeline.processTasks()
                raw = raw_queue.tryGet()
                if raw is not None:
                    validate_frame(raw, dai.ImgFrame.Type.NV12)
                    validated = True
                frame = encoded_queue.tryGet()
                if frame is not None and validated:
                    sender.submit(bytes(frame.getData()))
                stop.wait(0.002)
    finally:
        sender.close()


if __name__ == "__main__":
    main()
