"""Preserved depth-colored fixed-view NAS point-cloud preset."""

from .pointcloud import build_pipeline as build_pointcloud


def build_pipeline(pipeline):
    return build_pointcloud(pipeline, colorized=False)
