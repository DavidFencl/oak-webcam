"""Compact text panel kept inside the central area of the video."""
import cv2
import numpy as np


def draw_panel(image, lines, mirror_text=False):
    height, width = image.shape[:2]
    panel_width = int(width * 0.60)
    padding = max(8, int(height * 0.018))
    line_height = max(16, int(height * 0.035))
    scale = height / 720 * 0.52
    thickness = max(1, round(height / 720))
    font = cv2.FONT_HERSHEY_SIMPLEX
    longest = max(cv2.getTextSize(line, font, scale, thickness)[0][0] for line in lines)
    if longest > panel_width - 2 * padding:
        scale *= (panel_width - 2 * padding) / longest
    panel_height = padding * 2 + line_height * len(lines)
    panel = np.full((panel_height, panel_width, 3), 20, dtype=np.uint8)
    for index, line in enumerate(lines):
        cv2.putText(panel, line, (padding, padding + (index + 1) * line_height - 5),
                    font, scale, (240, 240, 240), thickness, cv2.LINE_AA)
    if mirror_text:
        panel = cv2.flip(panel, 1)
    # Keep clear of the upper/outer frame, which Meet can crop for self-view.
    x = (width - panel_width) // 2
    y = min(int(height * 0.64), height - panel_height - int(height * 0.16))
    image[y:y + panel_height, x:x + panel_width] = panel
    return image
