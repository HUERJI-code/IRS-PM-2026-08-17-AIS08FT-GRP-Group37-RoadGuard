"""Opt-in, local-only pixel inference. Checkpoints must be explicitly trusted.

PyTorch checkpoints can contain executable pickle data. SHA verification identifies
the operator-approved artifact; it does not make an untrusted checkpoint safe.
"""

import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

from PIL import Image

from roadguard.config import REPOSITORY_ROOT
from roadguard.errors import AppError
from roadguard.images import PreparedImage
from roadguard.schemas import Detection
from roadguard.schemas.common import LABELS_BY_ID


MANIFEST_VERSION = "roadguard-model-v1"
MAX_DETECTIONS = 100


def _unavailable():
    return AppError("detector_unavailable", "The local real detector is unavailable. Configure a trusted model manifest and installed vision dependencies.", 503)


def _inference_failed():
    return AppError("detector_inference_failed", "Real image inference failed; no inspection was created.", 502)


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest field")
        result[key] = value
    return result


def source_class_names():
    labels = json.loads((REPOSITORY_ROOT / "SystemCode/model/label_schema.json").read_text(encoding="utf-8"))
    return [item["source_name"] for item in sorted(labels["classes"], key=lambda item: item["class_id"])]


class LocalVisionDetector:
    """Lazy registry entry with serialized load/predict; no model download or fallback.

    model_loader is a dependency-injection seam for tests. Production imports YOLO
    only after the local file, digest, manifest and eight source labels validate.
    """

    def __init__(self, manifest_path: Path | None, *, model_loader=None):
        self.manifest_path = manifest_path
        self._model_loader = model_loader
        self._lock = Lock()
        self._model = None
        self._load_failed = False
        self.model_version = None
        self.weights_sha256 = None
        self.manifest_version = MANIFEST_VERSION
        self._inference = None

    def _load(self):
        if self._model is not None:
            return
        if self.manifest_path is None or self._load_failed:
            raise _unavailable()
        try:
            def invalid_constant(value):
                raise ValueError("invalid manifest number")
            manifest = json.loads(Path(self.manifest_path).read_text(encoding="utf-8"),
                                  object_pairs_hook=_unique_json, parse_constant=invalid_constant)
            names = source_class_names()
            if (manifest["schema_version"] != MANIFEST_VERSION or manifest["status"] != "experimental"
                    or manifest["source_class_names"] != names
                    or not isinstance(manifest["model_version"], str)
                    or not manifest["model_version"].strip()
                    or manifest["model_version"].strip().startswith("demo")):
                raise ValueError("unsupported model provenance")
            dataset = manifest["source_dataset"]
            if dataset["ref"] != "juusos/rdd2022es" or type(dataset["version"]) is not int or dataset["version"] != 1:
                raise ValueError("wrong source dataset")
            source_digest = dataset["manifest_sha256"]
            if (not isinstance(source_digest, str) or len(source_digest) != 64
                    or any(c not in "0123456789abcdef" for c in source_digest)):
                raise ValueError("invalid source manifest digest")
            sha = manifest["weights_sha256"]
            if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("invalid digest")
            value = manifest["weights_path"]
            if not isinstance(value, str) or not value.strip() or "://" in value:
                raise ValueError("local weights path required")
            weights = Path(value)
            # File opening below is authoritative. Non-strict resolution also works
            # in Windows sandboxes that deny realpath handle inspection.
            weights = (weights if weights.is_absolute() else REPOSITORY_ROOT / weights).resolve()
            if not weights.is_file() or weights.suffix.lower() != ".pt":
                raise ValueError("local PyTorch checkpoint required")
            digest = hashlib.sha256()
            with weights.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != sha:
                raise ValueError("checkpoint digest mismatch")
            inference = manifest["inference"]
            if set(inference) != {"conf", "iou", "imgsz"}:
                raise ValueError("unsupported inference settings")
            if (any(type(inference[key]) not in (int, float) or not math.isfinite(inference[key])
                    or not 0 < inference[key] <= 1 for key in ("conf", "iou"))
                    or type(inference["imgsz"]) is not int or not 32 <= inference["imgsz"] <= 1280):
                raise ValueError("unbounded inference settings")
            loader = self._model_loader
            if loader is None:
                os.environ["YOLO_OFFLINE"] = "true"
                os.environ["YOLO_AUTOINSTALL"] = "false"
                runtime_path = REPOSITORY_ROOT / "Dataset/tool-cache/ultralytics-backend"
                runtime_path.mkdir(parents=True, exist_ok=True)
                os.environ["YOLO_CONFIG_DIR"] = str(runtime_path)
                from ultralytics import YOLO, settings
                settings.update({key: False for key in (
                    "sync", "clearml", "comet", "dvc", "hub", "mlflow", "neptune",
                    "raytune", "tensorboard", "wandb",
                ) if key in settings})
                loader = YOLO
            model = loader(str(weights), task="detect")
            actual = model.names
            if isinstance(actual, dict):
                if set(actual) != set(range(8)):
                    raise ValueError("wrong model class IDs")
                actual = [actual[index] for index in range(8)]
            if actual != names or getattr(model, "task", "detect") != "detect":
                raise ValueError("wrong checkpoint names or task")
            self.model_version = manifest["model_version"].strip()
            self.weights_sha256 = sha
            self._inference = dict(inference)
            self._model = model
        except Exception:
            self._load_failed = True
            raise _unavailable() from None

    def detect(self, image: PreparedImage) -> list[Detection]:
        with self._lock:
            self._load()
            try:
                with Image.open(BytesIO(image.content)) as source:
                    pixels = source.convert("RGB")
                    if pixels.size != (image.width, image.height):
                        raise ValueError("inconsistent prepared image")
                    results = self._model.predict(source=pixels, **self._inference,
                                                  device="cpu", max_det=MAX_DETECTIONS,
                                                  verbose=False, save=False, stream=False)
                if len(results) != 1 or tuple(results[0].orig_shape) != (image.height, image.width):
                    raise ValueError("wrong inference image dimensions")
                boxes = results[0].boxes
                if boxes is None:
                    raise ValueError("missing detection output")
                coordinates = boxes.xyxy.cpu().tolist()
                classes, scores = boxes.cls.cpu().tolist(), boxes.conf.cpu().tolist()
                if not (len(coordinates) == len(classes) == len(scores) <= MAX_DETECTIONS):
                    raise ValueError("invalid detection count")
                output = []
                prefix = uuid4().hex
                for index, (box, class_id, score) in enumerate(zip(coordinates, classes, scores)):
                    if type(class_id) not in (int, float) or not math.isfinite(class_id) or int(class_id) != class_id:
                        raise ValueError("invalid predicted class ID")
                    class_id = int(class_id)
                    output.append(Detection(
                        detection_id=f"real-{prefix}-{index}", class_id=class_id,
                        label=LABELS_BY_ID[class_id], confidence=score, bbox_xyxy=tuple(box),
                        image_width=image.width, image_height=image.height,
                        model_version=self.model_version, is_demo=False,
                    ))
                return output
            except Exception:
                raise _inference_failed() from None
