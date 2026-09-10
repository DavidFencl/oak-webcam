import socket
import struct
import tempfile
import time
import unittest
from pathlib import Path

from main import validate_frame
from transport import FrameSender, MAX_FRAME_BYTES, pack_frame


def jpeg(payload):
    return b"\xff\xd8" + payload + b"\xff\xd9"


def receive_exact(connection, length):
    result = bytearray()
    while len(result) < length:
        chunk = connection.recv(length - len(result))
        if not chunk:
            raise EOFError("Partial packet")
        result.extend(chunk)
    return bytes(result)


def receive_frame(connection):
    length = struct.unpack("!I", receive_exact(connection, 4))[0]
    return receive_exact(connection, length)


class TransportTests(unittest.TestCase):
    def test_wire_format_and_rejected_frames(self):
        frame = jpeg(b"payload")
        self.assertEqual(pack_frame(frame), struct.pack("!I", len(frame)) + frame)
        for invalid in (b"", b"not jpeg", jpeg(b"x" * MAX_FRAME_BYTES)):
            with self.assertRaises(ValueError):
                pack_frame(invalid)

    def test_late_server_receives_latest_pending_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "bridge.sock")
            sender = FrameSender(path, timeout=0.1, retry_delay=0.01).start()
            try:
                sender.submit(jpeg(b"stale"))
                sender.submit(jpeg(b"latest"))
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                    server.bind(path)
                    server.listen(1)
                    server.settimeout(2)
                    connection, _ = server.accept()
                    with connection:
                        connection.settimeout(2)
                        self.assertEqual(receive_frame(connection), jpeg(b"latest"))
                        sender.submit(jpeg(b"next"))
                        self.assertEqual(receive_frame(connection), jpeg(b"next"))
            finally:
                sender.close()

    def test_reconnect_after_bridge_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "bridge.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(path)
                server.listen(2)
                server.settimeout(2)
                sender = FrameSender(path, timeout=0.1, retry_delay=0.01).start()
                try:
                    connection, _ = server.accept()
                    connection.shutdown(socket.SHUT_RDWR)
                    connection.close()
                    sender.submit(jpeg(b"failed write"))
                    connection, _ = server.accept()
                    with connection:
                        connection.settimeout(2)
                        sender.submit(jpeg(b"reconnected"))
                        self.assertEqual(receive_frame(connection), jpeg(b"reconnected"))
                finally:
                    sender.close()

    def test_stop_without_bridge_is_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            sender = FrameSender(str(Path(directory) / "missing.sock")).start()
            started = time.monotonic()
            sender.close()
            self.assertLess(time.monotonic() - started, 1)

    def test_slow_consumer_does_not_block_submit_or_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "bridge.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(path)
                server.listen(1)
                server.settimeout(2)
                sender = FrameSender(path, timeout=0.1, retry_delay=0.01).start()
                connection, _ = server.accept()
                try:
                    frame = jpeg(b"x" * (MAX_FRAME_BYTES - 4))
                    started = time.monotonic()
                    for _ in range(10):
                        sender.submit(frame)
                    self.assertLess(time.monotonic() - started, 1)
                    sender.close()
                    self.assertLess(time.monotonic() - started, 1.5)
                finally:
                    connection.close()
                    sender.close()

    def test_custom_output_contract(self):
        class Frame:
            def getWidth(self):
                return 1280

            def getHeight(self):
                return 720

            def getType(self):
                return "NV12"

        with self.assertRaisesRegex(ValueError, "3840x2160 NV12"):
            validate_frame(Frame(), "NV12")


if __name__ == "__main__":
    unittest.main()
