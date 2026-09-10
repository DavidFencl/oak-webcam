"""Bounded, display-server-free rendering of metric XYZ points to BGR video."""

from dataclasses import dataclass
import math
import os

import cv2
import numpy as np


@dataclass(frozen=True)
class View:
    """Fixed orbit camera in optical coordinates (X right, Y down, Z forward)."""

    yaw: float = 15.0
    pitch: float = -5.0
    distance: float = 1.5
    target: float = 1.0
    fov: float = 70.0

    def __post_init__(self):
        for name, lower, upper in (
            ("yaw", -80, 80), ("pitch", -80, 80),
            ("distance", 0.2, 15), ("target", 0.2, 15), ("fov", 20, 120),
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"Point-cloud {name} must be between {lower} and {upper}")

    @classmethod
    def from_env(cls):
        defaults = cls()
        return cls(**{
            name: float(os.environ.get(f"OAK_WEBCAM_POINTCLOUD_{name.upper()}", getattr(defaults, name)))
            for name in ("yaw", "pitch", "distance", "target", "fov")
        })

    def transform(self, points):
        yaw, pitch = np.deg2rad([self.yaw, self.pitch])
        right = np.array([np.cos(yaw), 0, np.sin(yaw)], dtype=np.float32)
        forward = np.array([-np.sin(yaw) * np.cos(pitch), -np.sin(pitch),
                            np.cos(yaw) * np.cos(pitch)], dtype=np.float32)
        down = np.cross(forward, right)
        target = np.array([0, 0, self.target], dtype=np.float32)
        position = target - self.distance * forward
        return (points - position) @ np.stack([right, down, forward]).T


class PointCloudRenderer:
    """Fixed projection; no scene-dependent zoom, centering, or color normalization."""

    def __init__(self, view=None, width=1280, height=720, max_points=100_000, radius=1):
        if not (1 <= width <= 3840 and 1 <= height <= 2160):
            raise ValueError("Invalid render size")
        if max_points < 1 or radius not in (0, 1, 2):
            raise ValueError("Invalid point budget or splat radius")
        self.view = view or View()
        self.width, self.height = width, height
        self.max_points, self.radius = max_points, radius
        self.focal = width / (2 * math.tan(math.radians(self.view.fov) / 2))
        self.background = np.array([20, 16, 12], dtype=np.uint8)

    def sample_indices(self, count, organized_shape=None):
        indices = np.arange(count)
        if organized_shape is not None and math.prod(organized_shape) == count:
            height, width = organized_shape
            step = max(1, math.ceil(math.sqrt(count / self.max_points)))
            indices = indices.reshape(height, width)[::step, ::step].reshape(-1)
        # Also caps odd-sized grids after ceil rounding.
        step = max(1, math.ceil(len(indices) / self.max_points))
        return indices[::step]

    def sample(self, points, organized_shape=None):
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        return points[self.sample_indices(len(points), organized_shape)]

    def render(self, points, organized_shape=None, colors=None):
        points = np.asarray(points, dtype=np.float32).reshape(-1, 3)
        indices = self.sample_indices(len(points), organized_shape)
        if colors is not None:
            colors = np.asarray(colors)
            if colors.ndim != 2 or colors.shape[0] != len(points) or colors.shape[1] not in (3, 4):
                raise ValueError("Colors must have one RGB or RGBA row per point")
            if colors.dtype != np.uint8:
                raise ValueError("Colors must use uint8 RGB values")
            colors = colors[indices, :3]
        points = points[indices]
        image = np.empty((self.height, self.width, 3), dtype=np.uint8)
        image[:] = self.background
        valid = np.isfinite(points).all(axis=1) & (points[:, 2] >= 0.2) & (points[:, 2] <= 8)
        points = self.view.transform(points[valid])
        front = np.isfinite(points).all(axis=1) & (points[:, 2] > 0.05)
        points = points[front]
        if colors is not None:
            colors = colors[valid][front]
        if not len(points):
            return image
        projected = points[:, :2] * (self.focal / points[:, 2, None])
        projected += [(self.width - 1) / 2, (self.height - 1) / 2]
        # Filter before int conversion: very large/offscreen coordinates cannot wrap.
        keep = ((projected[:, 0] >= -self.radius - 0.5) &
                (projected[:, 0] < self.width + self.radius - 0.5) &
                (projected[:, 1] >= -self.radius - 0.5) &
                (projected[:, 1] < self.height + self.radius - 0.5))
        pixels = np.floor(projected[keep] + 0.5).astype(np.int32)
        depths = points[keep, 2]
        if colors is not None:
            colors = colors[keep].astype(np.uint32)
            # Packed RGB is a deterministic tie-breaker for equal-depth samples.
            packed = (colors[:, 0] << 16) | (colors[:, 1] << 8) | colors[:, 2]
        zbuffer = np.full(self.width * self.height, np.inf, dtype=np.float32)
        # Every splat pixel participates in the z-buffer, including its edges.
        for dy in range(-self.radius, self.radius + 1):
            for dx in range(-self.radius, self.radius + 1):
                x, y = pixels[:, 0] + dx, pixels[:, 1] + dy
                inside = (x >= 0) & (x < self.width) & (y >= 0) & (y < self.height)
                np.minimum.at(zbuffer, y[inside] * self.width + x[inside], depths[inside])
        visible = np.isfinite(zbuffer)
        if colors is not None:
            winners = np.full(self.width * self.height, np.iinfo(np.uint32).max, dtype=np.uint32)
            for dy in range(-self.radius, self.radius + 1):
                for dx in range(-self.radius, self.radius + 1):
                    x, y = pixels[:, 0] + dx, pixels[:, 1] + dy
                    inside = (x >= 0) & (x < self.width) & (y >= 0) & (y < self.height)
                    locations = y[inside] * self.width + x[inside]
                    closest = depths[inside] == zbuffer[locations]
                    np.minimum.at(winners, locations[closest], packed[inside][closest])
            rgb = winners[visible]
            image.reshape(-1, 3)[visible] = np.stack([rgb & 255, (rgb >> 8) & 255, rgb >> 16], axis=1)
            return image
        # Fixed 0.2–8 metre virtual-camera depth scale: nearer red, farther blue.
        values = np.clip((8 - zbuffer[visible]) / 7.8 * 255, 0, 255).astype(np.uint8)
        if len(values):
            image.reshape(-1, 3)[visible] = cv2.applyColorMap(values, cv2.COLORMAP_TURBO).reshape(-1, 3)
        return image
