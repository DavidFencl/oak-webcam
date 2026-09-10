"""Local HTTP console and exclusive camera-worker supervisor (standard library only)."""
from dataclasses import asdict
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit, quote

from presets.config import PRESETS, selected_name
from pipeline import validate_custom_path
from transport import MAX_FRAME_BYTES, pack_frame

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
POINTCLOUD_PRESETS = ("pointcloud", "pointcloud-depth")


def validate_view(value=None, defaults=None):
    from presets.pointcloud_renderer import View
    base = defaults if defaults is not None else asdict(View.from_env())
    if value is None:
        return dict(base)
    if not isinstance(value, dict) or set(value) - set(base):
        raise ValueError("Point-cloud view must contain only yaw, pitch, distance, target and fov")
    if any(isinstance(number, bool) or not isinstance(number, (int, float)) for number in value.values()):
        raise ValueError("Point-cloud view values must be numbers")
    return asdict(View(**{**base, **value}))


class Supervisor:
    def __init__(self, directory, *, spawn=subprocess.Popen, ready_timeout=120):
        self.directory = Path(directory)
        self.spawn = spawn
        self.ready_timeout = ready_timeout
        self.lock = threading.RLock()
        self.operation = threading.Lock()
        self.stopped = threading.Event()
        self.worker = None
        self.preparation = None
        self.worker_dir = None
        self.current = None
        self.current_path = None
        self.current_view = None
        self.default_view = validate_view()
        self.target = None
        self.target_path = None
        self.target_view = None
        self.phase = "starting"
        self.error = None
        self.thread = None
        mode = PRESETS[selected_name()]
        self.usb = {key: int(os.environ.get("OAK_WEBCAM_" + key.upper(), getattr(mode, key)))
                    for key in ("width", "height", "fps")}

    def snapshot(self):
        with self.lock:
            data = {"phase": self.phase, "preset": self.current, "target": self.target,
                    "error": self.error, "usb": self.usb, "frames": 0, "frame_age": None,
                    "custom_path": self.current_path, "target_path": self.target_path,
                    "view": self.current_view, "target_view": self.target_view, "default_view": self.default_view,
                    "presets": [{"name": name, "description": p.description,
                                 "width": p.width, "height": p.height, "fps": p.fps}
                                for name, p in PRESETS.items()]}
            if self.worker_dir:
                try:
                    status = json.loads((self.worker_dir / "status.json").read_text())
                    data.update(frames=status["frames"], frame_age=max(0, time.monotonic() - status["monotonic"]))
                except (OSError, ValueError, KeyError):
                    pass
            if self.phase == "running":
                if self.worker is None or self.worker.poll() is not None:
                    data.update(phase="error", error="Camera worker exited; select a preset to restart.")
                elif data["frame_age"] is None or data["frame_age"] > 5:
                    data.update(phase="stalled", error="No recent encoded frames; select a preset to restart.")
            return data

    def preview(self):
        with self.lock:
            directory = self.worker_dir
            status = self.snapshot()
        if directory is None or status["frame_age"] is None or status["frame_age"] > 5:
            return None
        try:
            with (directory / "preview.jpg").open("rb") as stream:
                image = stream.read(MAX_FRAME_BYTES + 1)
            return image if 4 <= len(image) <= MAX_FRAME_BYTES else None
        except OSError:
            return None

    def request(self, name, path=None, view=None):
        if name not in PRESETS:
            raise ValueError("Unknown preset")
        if name == "custom":
            path = validate_custom_path(path)
        elif path is not None:
            raise ValueError("A file path is only supported for the custom pipeline")
        if name in POINTCLOUD_PRESETS:
            view = validate_view(view, self.current_view or self.default_view)
        elif view is not None:
            raise ValueError("View settings are only supported for point-cloud pipelines")
        if self.stopped.is_set() or not self.operation.acquire(blocking=False):
            raise RuntimeError("A pipeline change is already in progress")
        with self.lock:
            self.target, self.target_path, self.target_view, self.phase, self.error = name, path, view, "switching", None
        self.thread = threading.Thread(target=self._switch, args=(name, path, view), name="pipeline-switch")
        self.thread.start()

    def _stop_worker(self):
        with self.lock:
            worker = self.worker
        if worker is not None:
            if worker.poll() is None:
                worker.terminate()
                try:
                    worker.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=10)
            # Do not start another process unless exit is confirmed.
            if worker.poll() is None:
                raise RuntimeError("Previous camera process did not stop")
        with self.lock:
            self.worker = None
            if self.worker_dir:
                shutil.rmtree(self.worker_dir, ignore_errors=True)
                self.worker_dir = None

    def _start_worker(self, name, path=None, view=None):
        if self.stopped.is_set():
            raise RuntimeError("Console is stopping")
        if name == "custom":
            path = validate_custom_path(path)
        directory = Path(tempfile.mkdtemp(prefix="worker-", dir=self.directory))
        environment = dict(os.environ, OAK_WEBCAM_PRESET=name, OAK_WEBCAM_STATUS_DIR=str(directory))
        environment.pop("OAK_WEBCAM_CUSTOM_PIPELINE", None)
        if name == "custom":
            environment["OAK_WEBCAM_CUSTOM_PIPELINE"] = path
        if view is not None:
            for key, value in view.items():
                environment["OAK_WEBCAM_POINTCLOUD_" + key.upper()] = str(value)
        for key, value in self.usb.items():
            environment["OAK_WEBCAM_" + key.upper()] = str(value)
        with self.lock:
            self.worker_dir = directory
            self.worker = self.spawn([sys.executable, "-u", str(ROOT / "main.py")], env=environment)
            worker = self.worker
        deadline = time.monotonic() + self.ready_timeout
        while not self.stopped.wait(0.1):
            if worker.poll() is not None:
                raise RuntimeError(f"{name} exited with status {worker.returncode} before producing video")
            try:
                status = json.loads((directory / "status.json").read_text())
                if status["pid"] == worker.pid and status["frames"] > 0 and 0 <= time.monotonic() - status["monotonic"] < 5:
                    return
            except (OSError, ValueError, KeyError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"{name} produced no encoded video within {self.ready_timeout:g}s")
        raise RuntimeError("Console is stopping")

    def _placeholder(self, message):
        import cv2
        import numpy as np
        canvas = np.full((self.usb["height"], self.usb["width"], 3), 22, dtype=np.uint8)
        cv2.putText(canvas, message, (80, self.usb["height"] // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, self.usb["width"] / 1600, (220, 220, 220), 3)
        if os.environ.get("OAK_WEBCAM_MIRROR_TEXT") == "1":
            canvas = cv2.flip(canvas, 1)
        ok, encoded = cv2.imencode(".jpg", canvas)
        if not ok:
            return
        deadline = time.monotonic() + 5
        while not self.stopped.is_set():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(1)
                    connection.connect(os.environ.get("OAK_WEBCAM_SOCKET", "/tmp/oak-webcam.sock"))
                    connection.sendall(pack_frame(encoded.tobytes()))
                    # Allow the bridge cache to latch this frame before producer EOF.
                    self.stopped.wait(0.1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    LOG.warning("Could not send transition frame to bridge")
                    return
                self.stopped.wait(0.1)

    def _prepare_face(self):
        self.preparation = subprocess.Popen([sys.executable, "-m", "presets.models"], cwd=ROOT)
        deadline = time.monotonic() + 300
        try:
            while self.preparation.poll() is None:
                if self.stopped.wait(0.1) or time.monotonic() > deadline:
                    raise RuntimeError("Face model preparation stopped or timed out")
            if self.preparation.returncode:
                raise RuntimeError("Face model preparation failed")
        finally:
            if self.preparation.poll() is None:
                self.preparation.terminate()
                try:
                    self.preparation.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.preparation.kill()
                    self.preparation.wait(timeout=5)
            self.preparation = None

    def _switch(self, name, path=None, view=None):
        previous, previous_path, previous_view = self.current, self.current_path, self.current_view
        try:
            if self.worker is None:
                self._placeholder("Starting camera...")
            if name == "face-attention":
                # Model preparation does not open a camera; retain old video while downloading.
                with self.lock:
                    self.phase = "preparing"
                self._prepare_face()
            with self.lock:
                self.phase = "switching"
            self._stop_worker()
            self._placeholder("Switching camera...")
            self._start_worker(name, path, view)
            with self.lock:
                self.current, self.current_path, self.phase, self.target = name, path, "running", None
                self.current_view = view
                self.target_path, self.target_view = None, None
        except Exception as error:
            LOG.exception("Pipeline change failed")
            with self.lock:
                self.error = str(error)
                self.phase = "error"
            if not self.stopped.is_set():
                try:
                    self._stop_worker()
                    self._placeholder("Pipeline failed; restoring camera...")
                    if previous:
                        with self.lock:
                            self.phase = "rolling-back"
                        self._start_worker(previous, previous_path, previous_view)
                        with self.lock:
                            self.current, self.current_path, self.current_view, self.phase = previous, previous_path, previous_view, "running"
                except Exception as rollback:
                    with self.lock:
                        self.phase = "error"
                        self.error += f"; rollback failed: {rollback}"
            with self.lock:
                self.target, self.target_path, self.target_view = None, None, None
        finally:
            self.operation.release()

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=30)
            if self.thread.is_alive():
                raise RuntimeError("Pipeline transition did not stop")
        self._stop_worker()


class ControlServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, supervisor, token):
        self.supervisor, self.token = supervisor, token
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_):
        pass  # Do not persist URLs or tokens.

    def respond(self, status, data, content_type="application/json"):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.respond(403, {"error": "Cross-origin requests are not allowed"})
            return False
        expected = "Bearer " + self.server.token
        if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
            self.respond(401, {"error": "Enter the console token from the app log"})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        assets = {"/": ("index.html", "text/html; charset=utf-8"),
                  "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                  "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path in assets:
            filename, mime = assets[path]
            return self.respond(200, (ROOT / "console" / filename).read_bytes(), mime)
        if not self.authorized():
            return
        if path == "/api/status":
            return self.respond(200, self.server.supervisor.snapshot())
        if path == "/api/preview.jpg":
            frame = self.server.supervisor.preview()
            return self.respond(200, frame, "image/jpeg") if frame else self.respond(503, {"error": "No recent frame"})
        self.respond(404, {"error": "Not found"})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != "/api/preset":
            return self.respond(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024 or self.headers.get_content_type() != "application/json":
                raise ValueError("Expected a small JSON request")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or not isinstance(body.get("preset"), str):
                raise ValueError("Expected a preset name")
            self.server.supervisor.request(body["preset"], body.get("path"), body.get("view"))
        except (ValueError, UnicodeError) as error:
            return self.respond(400, {"error": str(error)})
        except RuntimeError as error:
            return self.respond(409, {"error": str(error)})
        self.respond(202, {"accepted": True})


def console_port():
    # The OAK-assigned port must win so oakctl's advertised URL is accurate.
    value = os.environ.get("OAKAPP_STATIC_FRONTEND_PORT") or os.environ.get("OAK_WEBCAM_CONTROL_PORT", "8080")
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError("Console port must be between 1 and 65535")
    return port


def console_urls(port, token):
    """List concrete IPv4 interface URLs without requiring internet access."""
    import fcntl
    import struct
    addresses = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        for _, name in socket.if_nameindex():
            try:
                result = fcntl.ioctl(probe.fileno(), 0x8915, struct.pack("256s", name.encode()[:15]))
                address = socket.inet_ntoa(result[20:24])
                if not address.startswith("127.") and address != "0.0.0.0":
                    addresses.add(address)
            except OSError:
                continue
    return [f"http://{address}:{port}/#token={quote(token, safe='')}" for address in sorted(addresses)]


def main():
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("OAK_WEBCAM_CONTROL_TOKEN") or secrets.token_urlsafe(24)
    port = console_port()
    stopped = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopped.set())
    with tempfile.TemporaryDirectory(prefix="oak-console-") as directory:
        supervisor = Supervisor(directory)
        server = ControlServer((os.environ.get("OAK_WEBCAM_CONTROL_BIND", "0.0.0.0"), port), supervisor, token)
        urls = console_urls(port, token)
        for url in urls:
            print(f"Webcam console: {url}", flush=True)
        if not urls:
            print(f"Console address unavailable; use the frontend URL from oakctl app list. Console token: {token}", flush=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            supervisor.request(selected_name(), os.environ.get("OAK_WEBCAM_CUSTOM_PIPELINE") if selected_name() == "custom" else None)
            stopped.wait()
        finally:
            server.shutdown()
            server.server_close()
            supervisor.close()


if __name__ == "__main__":
    main()
