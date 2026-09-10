"""Bounded latest-frame evidence shared by the worker and control process."""
import json
import os
from pathlib import Path
import time


def atomic_write(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


class FrameStatus:
    def __init__(self):
        directory = os.environ.get("OAK_WEBCAM_STATUS_DIR")
        self.directory = Path(directory) if directory else None
        self.count = 0
        self.last_write = 0.0

    def update(self, jpeg):
        self.count += 1
        now = time.monotonic()
        if self.directory is None or now - self.last_write < 1:
            return
        # Publish image first, then its metadata. Each worker has its own directory.
        atomic_write(self.directory / "preview.jpg", jpeg)
        atomic_write(self.directory / "status.json", json.dumps({
            "frames": self.count, "monotonic": now, "pid": os.getpid(),
        }).encode())
        self.last_write = now
