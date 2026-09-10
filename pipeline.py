"""Load a prepared preset or a trusted Python file in the camera worker.

Custom files export build_pipeline(pipeline), returning one Node.Output with
NV12 frames matching OAK_WEBCAM_WIDTH/HEIGHT. The runtime owns the lifecycle.
"""
from importlib import import_module, util
import os
from pathlib import Path
import sys

from presets.config import selected, selected_name


def validate_custom_path(value):
    """Validate without importing/executing code in the control process."""
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise ValueError("Provide an absolute path to a Python file on the OAK")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ValueError("Custom pipeline path must be absolute and refer to the OAK filesystem")
    try:
        candidate = candidate.resolve(strict=True)
        if candidate.suffix != ".py" or not candidate.is_file():
            raise ValueError("Custom pipeline must be a .py file")
        with candidate.open("rb"):
            pass
    except (OSError, RuntimeError) as error:
        raise ValueError(f"Cannot read custom pipeline: {error}") from error
    return str(candidate)


def load_custom_builder(value):
    path = validate_custom_path(value)
    specification = util.spec_from_file_location("oak_webcam_custom", path)
    if specification is None or specification.loader is None:
        raise ValueError("Cannot load custom pipeline module")
    module = util.module_from_spec(specification)
    sys.modules[specification.name] = module
    # Permit sibling helpers without requiring custom projects to be installed.
    sys.path.insert(0, str(Path(path).parent))
    specification.loader.exec_module(module)
    builder = getattr(module, "build_pipeline", None)
    if not callable(builder):
        raise ValueError("Custom pipeline must define build_pipeline(pipeline)")
    return builder


def build_pipeline(pipeline):
    if selected_name() == "custom":
        return load_custom_builder(os.environ.get("OAK_WEBCAM_CUSTOM_PIPELINE"))(pipeline)
    return import_module(f"presets.{selected().module}").build_pipeline(pipeline)
