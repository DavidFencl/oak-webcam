# Live preset console and point-cloud validation

Device: serial 1259426771, reported OAK4-D R7, Luxonis OS 1.40.0, DepthAI 3.10.0. Standalone app on the OAK; no competing camera process was started. Google Meet remained the USB consumer.

## Observed output

The console API switched between NAS, RGB 1080p, RGB 4K, LENS XL, RGB-colored point cloud, depth-colored point cloud, face-attention and the custom example `/app/examples/custom_rgb.py`. For each, a fresh encoded JPEG and status were fetched from the running app and decoded/visually inspected. Prepared 1080p source produced 3840×2160 output within an established 4K session. Evidence is local under `evidence/2026-09-10-live-console/` and excluded from git, including room/person images and redacted startup logs.

User-provided Google Meet screenshots independently confirm both depth-colored and RGB-colored point-cloud video reaching the USB consumer. API frame counts prove fresh encoding, not USB throughput. No new USB FPS benchmark was performed.

NAS extended disparity with subpixel disabled built and produced valid colorized depth on this device. This setting is intended for nearer surfaces; no calibrated minimum-distance or accuracy claim was measured. Point-cloud rendering filters physical depth outside 0.2–8 m.

## View framing

An initial offset view displaced nearby subjects out of frame. A physical-camera view restored framing but made RGB geometry appear flat. The revised angled default targets the nearby scene (yaw 15°, pitch −5°, distance 1.5 m, target 1 m), with bounded near-subject regression tests. Missing surfaces behind foreground objects remain holes because they were not observed by the physical camera; this is a live point cloud, not a reconstructed mesh.

## Automated and browser checks

All 38 Python tests passed, exercising preset contracts, custom file loading and sibling imports, invalid paths, worker exclusivity, readiness timeout/failure rollback, custom-path/view rollback, API authorization/origin rejection, frame freshness, projection, near framing, color association and occlusion. Native tests passed for producer reconnect, retained complete frames and late consumer access. Eight fake-configfs tests passed for USB setup/cleanup. Socket tests require execution outside the filesystem sandbox's socket restrictions.

Mock browser tests exercised preset switching, custom-path submission and view controls at desktop/mobile widths without JavaScript errors. A real browser session applied yaw 20° to the live RGB point cloud and then restored the default angled view; both changes completed with fresh encoded frames and no JavaScript errors. Token-free state and an inspected screenshot are saved under `evidence/live-console/view-controls.json` and `final-console.png`. No access token is included in shared documentation.

Standalone holistic replay and packaged `.oakapp` installation remain pending. Console HTTP is intended for a trusted local network. Mirrored text is enabled for this user's Meet self-view; unmirrored consumers see reversed overlay/transition text with that option.

## Frontend URL registration

The manifest now requests an assigned frontend port, and the HTTP console prioritizes `OAKAPP_STATIC_FRONTEND_PORT` over its local fallback. A rebuilt live app appeared in `oakctl app list` with `http://172.22.176.178:9000`; authenticated status and a fresh JPEG were fetched successfully from that assigned port. All 40 Python tests passed, including assigned-port precedence and range checks. The manifest also gives bounded worker shutdown and USB cleanup a 45-second stop grace period.
