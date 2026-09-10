"""Dependency-free preset registry shared by Python and USB startup."""

import argparse
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Preset:
    module: str
    width: int
    height: int
    fps: int
    description: str


PRESETS = {
    "rgb-1080p": Preset("rgb", 1920, 1080, 30, "RGB 1080p at 30 FPS"),
    "rgb-4k": Preset("rgb", 3840, 2160, 30, "RGB 4K at 30 FPS requested"),
    "lens-xl": Preset("lens_xl", 3840, 2160, 30, "LENS XL depth, about 9 new frames/s, upscaled to 4K"),
    "nas": Preset("nas", 3840, 2160, 30, "Neural Assisted Stereo depth, 30 FPS requested, upscaled to 4K"),
    "pointcloud": Preset("pointcloud", 3840, 2160, 30, "RGB-colored NAS point cloud, fixed view rendered at 720p and upscaled to 4K"),
    "pointcloud-depth": Preset("pointcloud_depth", 3840, 2160, 30, "Depth-colored NAS point cloud, fixed view rendered at 720p and upscaled to 4K"),
    "face-attention": Preset("face_attention", 3840, 2160, 30, "Facial expression and head direction, 20 FPS input, upscaled to 4K"),
    "custom": Preset("custom", 3840, 2160, 30, "User-provided Python pipeline file"),
}
DEFAULT_PRESET = "face-attention"


def selected_name():
    name = os.environ.get("OAK_WEBCAM_PRESET", DEFAULT_PRESET)
    if name not in PRESETS:
        raise ValueError(f"Unknown OAK_WEBCAM_PRESET {name!r}; choose: {', '.join(PRESETS)}")
    return name


def selected():
    return PRESETS[selected_name()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usb", action="store_true", help="Print width height FPS for USB startup")
    args = parser.parse_args()
    if args.usb:
        mode = selected()
        print(mode.width, mode.height, mode.fps)
    else:
        for name, mode in PRESETS.items():
            print(f"{name:18} {mode.description}")
