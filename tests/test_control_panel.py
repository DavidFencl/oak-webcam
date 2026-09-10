import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from control_panel import ControlServer, Supervisor, validate_view, console_port


class ConsolePortTests(unittest.TestCase):
    def test_oak_assigned_port_matches_advertised_frontend(self):
        with patch.dict(os.environ, {'OAKAPP_STATIC_FRONTEND_PORT': '8123',
                                     'OAK_WEBCAM_CONTROL_PORT': '9000'}, clear=True):
            self.assertEqual(console_port(), 8123)

    def test_local_fallback_and_invalid_port(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(console_port(), 8080)
            os.environ['OAK_WEBCAM_CONTROL_PORT'] = '9000'
            self.assertEqual(console_port(), 9000)
            os.environ['OAKAPP_STATIC_FRONTEND_PORT'] = '65536'
            with self.assertRaises(ValueError):
                console_port()
from runtime_status import FrameStatus


class FakeWorker:
    next_pid = 900
    def __init__(self, events, name, directory, fail=False):
        FakeWorker.next_pid += 1
        self.pid, self.returncode = FakeWorker.next_pid, None
        self.events, self.name = events, name
        events.append(('start', name))
        if fail:
            self.returncode = 1
        else:
            Path(directory, 'status.json').write_text(json.dumps({
                'pid': self.pid, 'frames': 1, 'monotonic': time.monotonic()}))
    def poll(self): return self.returncode
    def terminate(self):
        self.events.append(('stop', self.name))
        self.returncode = 0
    def wait(self, timeout=None):
        self.events.append(('reap', self.name))
        return self.returncode
    def kill(self): self.returncode = -9


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.events = []
        self.fail = set()
        def spawn(command, env):
            return FakeWorker(self.events, env['OAK_WEBCAM_PRESET'], env['OAK_WEBCAM_STATUS_DIR'],
                              env['OAK_WEBCAM_PRESET'] in self.fail)
        with patch.dict(os.environ, OAK_WEBCAM_PRESET='rgb-4k'):
            self.supervisor = Supervisor(self.temp.name, spawn=spawn, ready_timeout=.2)
        self.supervisor._placeholder = lambda message: None
    def tearDown(self):
        self.supervisor.close()
        self.temp.cleanup()
    def change(self, name, path=None, view=None):
        self.supervisor.request(name, path, view)
        self.supervisor.thread.join(3)
        self.assertFalse(self.supervisor.thread.is_alive())
    def test_handover_reaps_old_worker_before_next_and_keeps_usb_mode(self):
        self.change('rgb-4k')
        self.change('rgb-1080p')
        self.assertEqual(self.events[:4], [('start','rgb-4k'), ('stop','rgb-4k'),
                                         ('reap','rgb-4k'), ('start','rgb-1080p')])
        self.assertEqual(self.supervisor.snapshot()['usb']['width'], 3840)
        self.assertEqual(len(list(Path(self.temp.name).iterdir())), 1)
    def test_failed_start_rolls_back_and_retains_error(self):
        self.change('rgb-4k')
        self.fail.add('rgb-1080p')
        self.change('rgb-1080p')
        status = self.supervisor.snapshot()
        self.assertEqual(status['preset'], 'rgb-4k')
        self.assertEqual(status['phase'], 'running')
        self.assertIn('exited', status['error'])
    def test_live_process_without_frame_times_out_and_rolls_back(self):
        self.change('rgb-4k')
        original_spawn = self.supervisor.spawn
        def no_frame(command, env):
            worker = original_spawn(command, env)
            if env['OAK_WEBCAM_PRESET'] == 'rgb-1080p':
                Path(env['OAK_WEBCAM_STATUS_DIR'], 'status.json').unlink()
            return worker
        self.supervisor.spawn = no_frame
        self.change('rgb-1080p')
        status = self.supervisor.snapshot()
        self.assertEqual(status['preset'], 'rgb-4k')
        self.assertEqual(status['phase'], 'running')
        self.assertIn('no encoded video', status['error'])
    def test_custom_path_passed_and_restored_on_rollback(self):
        custom = Path(self.temp.name, 'mine.py')
        custom.write_text('def build_pipeline(pipeline): return pipeline\n')
        seen = []
        original_spawn = self.supervisor.spawn
        def capture(command, env):
            seen.append((env['OAK_WEBCAM_PRESET'], env.get('OAK_WEBCAM_CUSTOM_PIPELINE')))
            return original_spawn(command, env)
        self.supervisor.spawn = capture
        self.change('custom', str(custom))
        self.assertEqual(self.supervisor.snapshot()['custom_path'], str(custom))
        self.fail.add('rgb-1080p')
        self.change('rgb-1080p')
        self.assertEqual(seen, [('custom', str(custom)), ('rgb-1080p', None), ('custom', str(custom))])
        self.assertEqual(self.supervisor.snapshot()['custom_path'], str(custom))
        self.assertEqual(self.supervisor.snapshot()['phase'], 'running')
    def test_invalid_custom_path_does_not_stop_running_camera(self):
        self.change('rgb-4k')
        before = list(self.events)
        with self.assertRaises(ValueError):
            self.supervisor.request('custom', '/missing/camera.py')
        self.assertEqual(self.events, before)
        self.assertEqual(self.supervisor.snapshot()['preset'], 'rgb-4k')
    def test_view_validation_rejects_unsafe_or_inapplicable_values(self):
        for value in [{'yaw': float('nan')}, {'yaw': True}, {'distance': 0}, {'fov': 121},
                      {'yaw': '15'}, {'wrong': 10}, []]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_view(value)
        self.change('rgb-4k')
        before = list(self.events)
        with self.assertRaises(ValueError):
            self.supervisor.request('rgb-4k', view={'yaw': 10})
        with self.assertRaises(ValueError):
            self.supervisor.request('pointcloud', view={'pitch': 81})
        self.assertEqual(self.events, before)
    def test_pointcloud_view_environment_and_rollback(self):
        seen = []
        original_spawn = self.supervisor.spawn
        def capture(command, env):
            seen.append((env['OAK_WEBCAM_PRESET'], env.get('OAK_WEBCAM_POINTCLOUD_YAW')))
            return original_spawn(command, env)
        self.supervisor.spawn = capture
        self.change('pointcloud', view={'yaw': 25, 'distance': 1.7})
        status = self.supervisor.snapshot()
        self.assertEqual(status['view']['yaw'], 25)
        self.assertEqual(status['view']['distance'], 1.7)
        self.fail.add('rgb-1080p')
        self.change('rgb-1080p')
        self.assertEqual(seen[0], ('pointcloud', '25'))
        self.assertEqual(seen[-1], ('pointcloud', '25'))
        self.assertEqual(self.supervisor.snapshot()['view'], status['view'])
        self.assertIsNone(self.supervisor.snapshot()['target_view'])
    def test_busy_and_unknown_changes_rejected(self):
        self.supervisor.operation.acquire()
        try:
            with self.assertRaises(RuntimeError): self.supervisor.request('rgb-4k')
            with self.assertRaises(ValueError): self.supervisor.request('invalid')
        finally: self.supervisor.operation.release()
    def test_dead_worker_and_stale_frames_are_not_running(self):
        self.change('rgb-4k')
        self.supervisor.worker.returncode = 1
        self.assertEqual(self.supervisor.snapshot()['phase'], 'error')
        self.supervisor.worker.returncode = None
        p = self.supervisor.worker_dir / 'status.json'
        data = json.loads(p.read_text()); data['monotonic'] -= 20; p.write_text(json.dumps(data))
        self.assertEqual(self.supervisor.snapshot()['phase'], 'stalled')
        self.assertIsNone(self.supervisor.preview())
    def test_frame_status_publishes_real_frames_and_throttles_preview(self):
        with patch.dict(os.environ, OAK_WEBCAM_STATUS_DIR=self.temp.name):
            reporter = FrameStatus()
        reporter.update(b'first')
        reporter.update(b'second')
        self.assertEqual(Path(self.temp.name, 'preview.jpg').read_bytes(), b'first')
        self.assertEqual(json.loads(Path(self.temp.name, 'status.json').read_text())['frames'], 1)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        class State:
            def snapshot(self): return {'phase': 'running'}
            def preview(self): return b'\xff\xd8\xff\xd9'
            def request(self, name, path=None, view=None):
                if name != 'rgb-4k': raise ValueError('Unknown preset')
        self.server = ControlServer(('127.0.0.1', 0), State(), 'test-token')
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
    def test_api_requires_token_and_rejects_cross_origin_even_with_token(self):
        for headers, code in [({}, 401), ({'Authorization':'Bearer test-token', 'Origin':'http://evil.invalid'}, 403)]:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(self.url + '/api/status', headers=headers))
            self.assertEqual(error.exception.code, code)
            error.exception.close()
        with urlopen(Request(self.url + '/api/status', headers={'Authorization':'Bearer test-token'})) as response:
            self.assertEqual(json.load(response)['phase'], 'running')
    def test_switch_and_malformed_json(self):
        headers={'Authorization':'Bearer test-token', 'Content-Type':'application/json'}
        with urlopen(Request(self.url + '/api/preset', data=b'{"preset":"rgb-4k"}', headers=headers)) as response:
            self.assertEqual(response.status, 202)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.url + '/api/preset', data=b'[]', headers=headers))
        self.assertEqual(error.exception.code, 400)
        error.exception.close()


if __name__ == '__main__': unittest.main()
