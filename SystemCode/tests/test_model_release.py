"""Release installer integrity and single-subject HTTP representation; no YOLO."""

import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model.install_released_model import install
from model.single_damage import select
from roadguard.schemas import Detection
from roadguard.schemas.common import LABELS_BY_ID
from roadguard.vision.primary import PrimaryPolicy
from roadguard.vision.suggestion import primary_suggestion
from roadguard.schemas.workflow import InspectionRecord


@pytest.fixture
def package(tmp_path):
    source = tmp_path / "download.pt"
    source.write_bytes(b"not-deserialized-unit-checkpoint")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"weights_path": "Dataset/models/model.pt", "weights_bytes": source.stat().st_size,
                                    "weights_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}))
    return tmp_path, source, manifest


def test_install_validates_atomically_and_is_idempotent(package):
    root, source, manifest = package
    destination = install(source, root=root, manifest_path=manifest)
    assert destination.read_bytes() == source.read_bytes()
    assert install(source, root=root, manifest_path=manifest) == destination
    assert not list(destination.parent.glob("*.partial"))


def test_install_rejects_changed_download_and_preserves_existing_model(package):
    root, source, manifest = package
    source.write_bytes(b"incorrect bytes")
    with pytest.raises(ValueError, match="SHA-256"):
        install(source, root=root, manifest_path=manifest)
    assert not (root / "Dataset/models").exists()


def test_install_never_overwrites_another_model(package):
    root, source, manifest = package
    destination = root / "Dataset/models/model.pt"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"preserve this")
    with pytest.raises(ValueError, match="no file was overwritten"):
        install(source, root=root, manifest_path=manifest)
    assert destination.read_bytes() == b"preserve this"


def test_installer_rejects_manifest_output_escape(package):
    root, source, manifest = package
    content = json.loads(manifest.read_text())
    content["weights_path"] = "../escaped.pt"
    manifest.write_text(json.dumps(content))
    with pytest.raises(ValueError, match="inside Dataset/models"):
        install(source, root=root, manifest_path=manifest)


def test_shared_real_response_example_is_review_only():
    root = Path(__file__).resolve().parents[2]
    record = InspectionRecord.model_validate_json((root / "SystemCode/contracts/workflow/real-primary-example.json").read_text())
    assert record.mode == "real" and record.primary_suggestion.detection_id in {d.detection_id for d in record.detections}
    assert record.status == "pending_review" and record.selected_detection_id is None and record.task_id is None


@pytest.mark.parametrize("scores,classes,boxes", [
    ([.9,.7], [6,4], [(0,0,5,5),(30,30,80,80)]),
    ([.8,.8], [6,7], [(10,10,30,30),(10,10,30,30)]),
    ([.8,.8], [6,6], [(10,10,30,30),(60,60,80,80)]),
    ([.1], [6], [(0,0,100,100)]), ([], [], []),
])
def test_persisted_suggestion_matches_evaluated_policy(scores, classes, boxes):
    detections = [Detection(detection_id=str(i), class_id=c, label=LABELS_BY_ID[c], confidence=s,
                            bbox_xyxy=b, image_width=100, image_height=100, model_version="test", is_demo=False)
                  for i, (s,c,b) in enumerate(zip(scores, classes, boxes))]
    policy = PrimaryPolicy("area_quarter", .2)
    expected, warning = select(detections, policy, False)
    result = primary_suggestion(detections, policy)
    assert result.detection_id == (expected.detection_id if expected else None)
    assert result.ambiguous == (warning["status"] == "ambiguous")
    assert result.competing_detection_ids == warning["competing_detection_ids"]
