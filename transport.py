"""Bounded, reconnecting MJPEG client for the native USB bridge."""

import logging
import socket
import struct
import threading

MAX_FRAME_BYTES = 1920 * 1080 * 2
LOG = logging.getLogger(__name__)


def pack_frame(frame):
    if not 4 <= len(frame) <= MAX_FRAME_BYTES:
        raise ValueError(f"JPEG size must be 4..{MAX_FRAME_BYTES} bytes")
    if frame[:2] != b"\xff\xd8" or frame[-2:] != b"\xff\xd9":
        raise ValueError("Encoded frame is not a complete JPEG")
    return struct.pack("!I", len(frame)) + frame


class FrameSender:
    """Only the newest pending frame survives a slow/disconnected consumer.

    Socket writes happen on a worker thread, never the pipeline control loop.
    A failed partial write closes the connection to reset framing at the bridge.
    """

    def __init__(self, path, timeout=0.5, retry_delay=0.25):
        self.path = path
        self.timeout = timeout
        self.retry_delay = retry_delay
        self._condition = threading.Condition()
        self._stopped = threading.Event()
        self._pending = None
        self._thread = threading.Thread(target=self._run, name="webcam-sender", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def submit(self, frame):
        packet = pack_frame(frame)
        with self._condition:
            if not self._stopped.is_set():
                self._pending = packet
                self._condition.notify()

    def close(self):
        self._stopped.set()
        with self._condition:
            self._pending = None
            self._condition.notify()
        if self._thread.ident is not None:
            self._thread.join(timeout=self.timeout + self.retry_delay + 1)
        if self._thread.is_alive():
            raise RuntimeError("Webcam sender did not stop")

    def _run(self):
        connection = None
        try:
            while not self._stopped.is_set():
                if connection is None:
                    candidate = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    candidate.settimeout(self.timeout)
                    try:
                        candidate.connect(self.path)
                    except OSError:
                        candidate.close()
                        self._stopped.wait(self.retry_delay)
                        continue
                    connection = candidate
                    LOG.info("Connected to webcam bridge at %s", self.path)
                with self._condition:
                    self._condition.wait_for(
                        lambda: self._pending is not None or self._stopped.is_set()
                    )
                    if self._stopped.is_set():
                        break
                    packet, self._pending = self._pending, None
                try:
                    connection.sendall(packet)
                except OSError:
                    connection.close()
                    connection = None
                    self._stopped.wait(self.retry_delay)
        finally:
            if connection is not None:
                connection.close()
