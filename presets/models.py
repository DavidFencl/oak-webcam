"""Download the supported RVC4 Zoo variants before enabling the USB gadget."""
import json
from pathlib import Path
import depthai as dai

REFERENCES = {
    "face": "luxonis/yunet:640x360",
    "expression": "luxonis/emotion-recognition:260x260",
    "pose": "luxonis/head-pose-estimation:60x60",
}
MANIFEST = Path("/tmp/oak-webcam-models.json")


def prepare():
    paths = {}
    for name, reference in REFERENCES.items():
        print(f"Preparing {reference} for RVC4", flush=True)
        description = dai.NNModelDescription(reference, platform="RVC4")
        paths[name] = str(dai.getModelFromZoo(description))
    MANIFEST.write_text(json.dumps(paths))


def archives():
    paths = json.loads(MANIFEST.read_text())
    return {name: dai.NNArchive(paths[name]) for name in REFERENCES}


if __name__ == "__main__":
    prepare()
