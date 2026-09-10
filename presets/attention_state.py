"""Visible head-direction timing; no mood, cognition, or identity measurement."""
import math


class FacingTimer:
    def __init__(self):
        self.last_timestamp = None
        self.started = None
        self.last_box = None

    def update(self, timestamp, yaw=None, pitch=None, box=None):
        gap = self.last_timestamp is None or not 0 < timestamp - self.last_timestamp <= 0.5
        # Geometric continuity, not identification.
        changed = self.last_box is not None and box is not None and box_iou(self.last_box, box) < 0.3
        facing = (yaw is not None and pitch is not None and
                  math.isfinite(yaw) and math.isfinite(pitch) and
                  abs(yaw) <= 20 and abs(pitch) <= 20)
        if gap or changed or not facing:
            self.started = None
        if facing and self.started is None:
            self.started = timestamp
        self.last_timestamp = timestamp
        self.last_box = box
        return facing, 0.0 if self.started is None else timestamp - self.started


def box_iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0.0
