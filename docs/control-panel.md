# Webcam control console

The app serves a browser console on the frontend port assigned by Luxonis.
Run `oakctl app list -d DEVICE_IP` and open the frontend URL it reports. Do not
assume port 8080: the assigned port can change after an app restart.

Read the app's startup logs for `Webcam console: .../#token=...`. Copy the value
after `#token=` into the console's **Console token** field and press **Connect**,
or append that fragment to the frontend URL. When using the log's URL directly,
replace `<device-ip>` with the device address. The token is generated per app
launch unless configured. The browser removes the fragment from the address bar
and retains it in memory only.

The console lists every registered preset, including NAS and pointcloud when
present. Choose a pipeline and press **Switch pipeline**, or **Apply pipeline
and fixed view** for point-cloud presets. It displays startup,
switching, rollback, errors, an encoded-frame count, age of the latest frame,
and a preview refreshed once per second. The preview is the outgoing image;
Google Meet's mirrored self-view may differ. The face preset's mirror-text option
therefore also applies to this preview. `OAK_WEBCAM_MIRROR_TEXT=1` preflips
transition-screen text as well as the face overlay, making both readable in a
mirrored self-view. Recipients and the unmirrored console preview see reversed
text with that option enabled.

The initial preset chooses the USB mode for the app session. All later presets
are resized to that same mode, so switching does not disconnect or re-enumerate
the USB camera. For example, starting `rgb-4k` and then selecting `rgb-1080p`
uses the 1080p source upscaled to the established 4K USB mode. Starting in 1080p
and selecting a 4K preset downscales its output. The console separately shows
preset output and USB output. Changing the USB mode itself requires an app
restart with a different initial preset.

Only one camera worker runs at a time. The supervisor completely stops and reaps
the previous worker before starting another. A transition image keeps the USB
stream populated while models/pipelines initialize. Face models are prepared
before stopping a current worker. Changes are serialized; another request while
a switch is pending returns HTTP 409. If the next pipeline exits or produces no
encoded frame within 120 seconds, the supervisor stops it and attempts to
restore the previous preset. A rollback failure remains visible in the console.
Selecting a preset again can recover from an exited/stalled worker.

The first validated encoded frame marks a worker ready. A process alone never
marks the camera ready, and five seconds without fresh frame metadata reports a
stall. This is evidence of encoded output; USB consumption still requires host
validation. The latest JPEG and status are replaced atomically once per second
in an owned temporary directory, with old worker directories removed after exit.
No frame history is recorded. The native bridge retains a transition image if
both startup and rollback fail; consult the console's error state.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `OAK_WEBCAM_PRESET` | `face-attention` | Initial pipeline and session USB mode |
| `OAK_WEBCAM_CONTROL_BIND` | `0.0.0.0` | Console listening interface |
| `OAKAPP_STATIC_FRONTEND_PORT` | Assigned by Luxonis | Registered frontend port; takes priority when present |
| `OAK_WEBCAM_CONTROL_PORT` | `8080` fallback | Console port only when no Luxonis frontend port is assigned |
| `OAK_WEBCAM_CONTROL_TOKEN` | Random per launch | Optional stable access token |

Use a trusted local network: the console is plain HTTP. API calls require a
Bearer token and reject mismatched browser origins. No CORS permissions are
granted. Do not include token-bearing log lines in shared evidence or PRs.

## API

`GET /api/status` returns current phase, preset/target, error, USB mode, frame
count/age and the preset registry. `GET /api/preview.jpg` returns the latest JPEG
or 503 if unavailable/stale. `POST /api/preset` accepts JSON
`{"preset":"nas"}` and returns 202 when the switch is accepted. Every API call
needs `Authorization: Bearer <token>`. This API performs asynchronous pipeline
changes; poll status to determine their outcome.

## Validation

` .venv/bin/python -m unittest discover -s tests -p 'test_*.py' ` covers ordered
worker teardown, failed-start rollback, concurrent request rejection, stale/dead
worker status, bounded snapshot publication, authentication/origin rejection,
and malformed requests. Device validation must separately demonstrate two
presets producing different fresh JPEGs across a switch while the USB gadget
stays bound. Standalone holistic replay remains pending.

## Load your own Python pipeline

Choose **custom**, enter an absolute path such as `/app/examples/custom_rgb.py`,
and press **Switch pipeline**. The path refers to the **OAK app's filesystem**,
not the browser's computer. Put your file in this repository before building the
app: `examples/mine.py` is available as `/app/examples/mine.py` in the app.
The bundled `examples/custom_rgb.py` is a minimal working reference.

A custom file exports `build_pipeline(pipeline)` and returns exactly one DepthAI
`Node.Output`. It must emit NV12 frames with the active USB width and height,
available in `OAK_WEBCAM_WIDTH` and `OAK_WEBCAM_HEIGHT`; the requested USB frame
rate is `OAK_WEBCAM_FPS`. The runtime owns starting/stopping the supplied pipeline
and MJPEG encoding. Do not start another camera or pipeline yourself. Unlike
prepared presets with declared source dimensions, custom output is validated
against the session's USB dimensions directly. Sibling Python helper imports
are supported within the custom file's directory.

You can also launch the app with `OAK_WEBCAM_PRESET=custom` and
`OAK_WEBCAM_CUSTOM_PIPELINE=/app/examples/custom_rgb.py`. Initial custom sessions
use 4K/30 FPS USB mode. A live switch uses whichever mode was established when
the app started.

API example: `POST /api/preset` with
`{"preset":"custom","path":"/app/examples/custom_rgb.py"}` and the normal
Bearer token. Status includes `custom_path` for the current custom worker and
`target_path` during a pending change. The supervisor validates an existing,
readable `.py` file before stopping the current camera. Import/build errors or
missing frames follow the same stop-and-rollback behavior as prepared presets;
rollback restores the previous custom file path when applicable.

Only load Python code you trust: custom files execute with the OAK app's full
permissions. The authenticated console accepts local file paths, not URLs or
file uploads. Path validation does not make Python code safe or sandbox it.

## Fix a point-cloud camera angle

The `pointcloud` and `pointcloud-depth` presets expose yaw, pitch, orbit distance,
look-at depth, and horizontal field of view in the console. Change the values and
press **Apply pipeline and fixed view**. The pipeline restarts, then keeps that
view fixed in the 2D video. USB dimensions stay unchanged. This is not a moving
orbit or an interactive 3D stream.

**Front view** uses yaw/pitch 0°, orbit distance 2 m, look-at depth 2 m and FOV 70°,
reproducing the physical camera viewpoint. **Angled view** restores the app's
configured default (15° yaw, −5° pitch, 1.5 m orbit distance, 1 m look-at depth,
70° FOV unless overridden with environment variables). A virtual viewpoint can
make depth more visible, while revealing holes on surfaces the physical cameras
did not observe. Orbit distance changes the distance from the virtual camera to
the look-at point; look-at depth moves that point along the physical camera's
forward axis.

API callers may include a `view` object, for example:
`{"preset":"pointcloud","view":{"yaw":25,"pitch":-5,"distance":1.5,"target":1,"fov":70}}`.
Partial view objects inherit the active point-cloud view, or the startup defaults
when none is active. Yaw and pitch accept −80…80°, distance and target 0.2…15 m,
and FOV 20…120°. Values must be finite numbers. Unknown settings and view objects
on other presets are rejected before stopping the current pipeline.

Status exposes effective `view`, pending `target_view`, and `default_view` for
control initialization. Failed changes roll back the previous view as well as
the previous preset. API/UI view changes last for the app session; environment
variables establish defaults across app restarts.
