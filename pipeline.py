"""Select a prepared pipeline with OAK_WEBCAM_PRESET.

Custom pipelines return one NV12 output matching presets.config.selected().
The runtime owns the pipeline lifecycle and MJPEG encoding.
"""
from importlib import import_module
from presets.config import selected


def build_pipeline(pipeline):
    return import_module(f"presets.{selected().module}").build_pipeline(pipeline)
