# Point-cloud webcam

Select `OAK_WEBCAM_PRESET=pointcloud` to stream a fixed perspective of the live 3D scene with real RGB surface colors as ordinary 2D webcam video. `pointcloud-depth` preserves the earlier depth-colored visualization. Neural Assisted Stereo supplies depth; the calibrated PointCloud node converts it into metric XYZ coordinates. A CPU renderer projects those points through a fixed virtual camera. The 1280×720 rendering is upscaled to 3840×2160 NV12 for MJPEG/USB. The 30 FPS USB mode is a transport setting; fresh rendered throughput depends on depth and CPU processing.

For RGB, undistorted CAM_A RGB888i frames at 1280×720 define the alignment target. ImageAlign reprojects NAS depth into that camera, then PointCloud internally pairs depth and color by timestamp. RGB input buffering retains up to 16 frames to accommodate inference latency. `getPointsRGB()` supplies corresponding XYZ and RGBA arrays; identical sampling/filtering preserves their association. The nearest surface wins each rendered pixel, carrying its own RGB color (converted to BGR for video). Equal-depth ties use a deterministic color order. This colors actual depth samples; it does not substitute a flat RGB image.

No desktop, OpenGL context, Open3D, or interactive 3D viewer is required. The view does not automatically orbit, zoom, or recenter as people move. This is a live single-camera point cloud, so moving the virtual camera reveals gaps and occluded surfaces remain missing. It is not a reconstructed or completed 3D mesh.

## Fixed view

Set these environment variables when starting the app. Coordinates use metres in the RGB camera's optical frame for `pointcloud`, and the left camera's frame for `pointcloud-depth`: X right, Y down, Z forward. The camera looks at `(0, 0, TARGET)` from `DISTANCE` metres away. Zero yaw/pitch gives a forward-facing view; positive yaw moves the virtual camera to the right of the target, and negative pitch moves it above the target.

| Variable prefix `OAK_WEBCAM_POINTCLOUD_` | Default | Range | Meaning |
|---|---:|---:|---|
| `YAW` | 15 | −80…80 | Horizontal orbit angle, degrees |
| `PITCH` | −5 | −80…80 | Vertical orbit angle, degrees |
| `DISTANCE` | 1.5 | 0.2…15 | Virtual camera distance from target, metres |
| `TARGET` | 1 | 0.2…15 | Target distance forward of the physical reference camera, metres |
| `FOV` | 70 | 20…120 | Horizontal field of view, degrees |

The default view is slightly oblique and backed away from the physical camera, looking toward a nearby one-metre target. This shows 3D parallax while retaining nearby subjects in frame. Its output uses the configured 70-degree horizontal field of view. For a front view matching the physical reference camera's position and orientation, use yaw/pitch zero and equal distance/target, for example 2 metres each. Oblique views expose holes behind foreground objects because the physical camera never observed those surfaces; changing the viewpoint cannot recover them. Values must be finite and in range. Restart the point-cloud pipeline after changing its environment.

Depth outside 0.2–8 metres from the physical reference camera is omitted. Only `pointcloud-depth` uses a fixed 0.2–8 metre depth color scale relative to the **virtual** camera, with warm nearby points and cool farther points. The renderer samples the organized depth grid spatially with a maximum of 100,000 points per frame. Each point covers 3×3 render pixels. A nearest-depth buffer resolves occlusion across the entire splat, independent of point arrival order. Invalid, behind-camera, and offscreen points are discarded.

## API sources and validation

DepthAI 3.10.0 Python bindings and the current Luxonis [PointCloud documentation](https://docs.luxonis.com/software-v3/depthai/depthai-components/host_nodes/pointcloud/) and [showcase](https://docs.luxonis.com/software-v3/depthai/examples/pointcloud/point_cloud_showcase/) verify `inputDepth`, `outputPointCloud`, metric length units, target camera coordinates, organized output and `getPoints()`. `setRunOnHost(True)` runs point-cloud generation on the OAK4's application CPU in this standalone deployment.

`tests/test_pointcloud.py` verifies occlusion, clipping, fixed view, metric target projection, bounded sampling and invalid settings without hardware. Synthetic renderer evidence belongs under `evidence/`; it proves projection behavior only. Both point-cloud presets produced decoded live frames on the OAK, with user screenshots confirming USB video in Meet. Live console controls changed yaw and restored the default view with fresh output after both changes; see [validation](validation-2026-09-10-live-console.md). Holistic replay is pending for this standalone USB path.
