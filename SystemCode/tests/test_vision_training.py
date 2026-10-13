"""Recovery/identity/cleanup contracts run in core CI without torch or Ultralytics."""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import checkpointing, evaluate, make_smoke, train


def test_atomic_publication_preserves_both_epochs_and_handles_replace_failure(tmp_path, monkeypatch):
    store = checkpointing.RecoveryStore(tmp_path)
    store.publish(b"epoch1 optimizer state")
    store.publish(b"epoch2 optimizer state")
    assert store.latest.read_bytes() == b"epoch2 optimizer state"
    assert store.previous.read_bytes() == b"epoch1 optimizer state"
    original = checkpointing.os.replace

    def fail_latest(source, target):
        if target == store.latest:
            raise OSError("simulated sudden publication failure")
        original(source, target)

    monkeypatch.setattr(checkpointing.os, "replace", fail_latest)
    with pytest.raises(OSError):
        store.publish(b"epoch3")
    assert store.latest.read_bytes() == b"epoch2 optimizer state"
    assert store.previous.read_bytes() == b"epoch2 optimizer state"
    assert not list(tmp_path.glob("*.tmp"))


def test_resume_requires_same_dataset_config_and_training_state():
    identity = {"config_sha256": "config", "manifest_sha256": "dataset"}
    checkpoint = {"epoch": 3, "optimizer": {"state": {1: "momentum"}},
                  "roadguard": {"identity": identity, "scheduler": {}, "rng": {}, "live_model_state": {}, "stopper": {}}}
    assert checkpointing.validate_resume(checkpoint, identity) == 4
    for identity_update in ({"manifest_sha256": "other"}, {"config_sha256": "changed"}):
        with pytest.raises(ValueError, match="mismatch"):
            checkpointing.validate_resume(checkpoint, {**identity, **identity_update})
    for update in ({"epoch": -1}, {"optimizer": None}, {"roadguard": {"identity": identity}}):
        with pytest.raises(ValueError):
            checkpointing.validate_resume({**checkpoint, **update}, identity)


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setattr(train, "REPO_ROOT", tmp_path)
    # local_path's default root is bound at definition time; explicit wrapper isolates test assets.
    original_local_path = train.local_path
    monkeypatch.setattr(train, "local_path", lambda value: original_local_path(value, tmp_path))
    monkeypatch.setattr(evaluate, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(evaluate, "local_path", lambda value: original_local_path(value, tmp_path))
    data = tmp_path / "Dataset" / "prepared"
    data.mkdir(parents=True)
    (data / "data.yaml").write_text("names: []")
    (data / "manifest.jsonl").write_text('{"split":"train"}\n')
    weights = tmp_path / "Dataset" / "pretrained"
    weights.mkdir()
    (weights / "yolo11n.pt").write_bytes(b"local pretrained")
    value = json.loads(Path(train.__file__).with_name("training.example.json").read_text())
    value["train"]["epochs"] = 2
    return value, tmp_path


def test_model_injected_training_reports_failure_and_never_silently_restarts(config):
    value, root = config
    runtime = {"python": "fake", "packages": {}, "platform": "fake"}

    class FakeModel:
        def __init__(self, path):
            assert Path(path).is_file()
        def add_callback(self, event, callback):
            assert event in {"on_model_save", "on_train_epoch_start", "on_train_end"}
        def train(self, **arguments):
            assert arguments["cache"] is False and arguments["save_period"] == -1
            raise train.TrainingInterrupted("fake interruption")

    with pytest.raises(train.TrainingInterrupted):
        train.run_training(value, model_factory=FakeModel, runtime=runtime)
    run_dir = root / "Dataset" / "runs" / value["run_name"]
    assert json.loads((run_dir / "run_status.json").read_text())["status"] == "interrupted"
    with pytest.raises(ValueError, match="Run already exists"):
        train.run_training(value, model_factory=FakeModel, runtime=runtime)


def test_training_fairness_records_actual_nominal_batch_and_warmup_state(tmp_path):
    config = {"train": {"batch": 32, "epochs": 30, "seed": 42, "amp": False}}
    trainer = SimpleNamespace(batch_size=32, args=SimpleNamespace(**config["train"], nbs=64),
                              accumulate=1, epoch=0)
    train.training_fairness_callback(config, tmp_path)(trainer)
    evidence = json.loads((tmp_path / "effective_training.json").read_text())
    assert evidence["actual_batch"] == evidence["configured_batch"] == evidence["argument_batch"] == 32
    assert evidence["nominal_accumulate"] == 2 and evidence["effective_nominal_batch"] == 64
    assert evidence["current_accumulate"] == 1 and evidence["epoch_1based"] == 1
    assert evidence["config_sha256"] == checkpointing.fingerprint(config)
    assert evidence["train_args_subset"] == config["train"]
    trainer.epoch, trainer.accumulate = 29, 2
    train.training_fairness_callback(config, tmp_path, event="train_end")(trainer)
    evidence = json.loads((tmp_path / "effective_training.json").read_text())
    assert evidence["epoch_1based"] == 30 and evidence["event"] == "train_end"


@pytest.mark.parametrize("changed_field", ["batch_size", "argument_batch", "both"])
def test_training_fairness_rejects_oom_batch_reduction_without_replacing_evidence(tmp_path, changed_field):
    config = {"train": {"batch": 32, "epochs": 30}}
    trainer = SimpleNamespace(batch_size=32, args=SimpleNamespace(**config["train"], nbs=64),
                              accumulate=2, epoch=0)
    callback = train.training_fairness_callback(config, tmp_path)
    callback(trainer)
    evidence = (tmp_path / "effective_training.json").read_bytes()
    if changed_field in {"batch_size", "both"}:
        trainer.batch_size = 16
    if changed_field in {"argument_batch", "both"}:
        trainer.args.batch = 16
    with pytest.raises(ValueError, match="Automatic OOM batch reduction"):
        callback(trainer)
    assert (tmp_path / "effective_training.json").read_bytes() == evidence


def fake_metrics():
    matrix = [[0] * 9 for _ in range(9)]
    matrix[0][0], matrix[1][0] = 2, 1
    class FakeMatrix:
        def tolist(self):
            return matrix
    box = SimpleNamespace(ap_class_index=[0], p=[0.5], r=[0.6], f1=[0.545], ap50=[0.7], ap=[0.4],
                          mp=0.5, mr=0.6, map50=0.7, map=0.4)
    return SimpleNamespace(names=evaluate.source_names(), box=box, nt_per_class=[3] + [0] * 7), SimpleNamespace(seen=2, confusion_matrix=SimpleNamespace(matrix=FakeMatrix()))


def test_report_preserves_eight_classes_absent_metrics_and_rejects_nan():
    metrics, validator = fake_metrics()
    report = evaluate.metrics_report(metrics, validator, evaluate.source_names())
    assert len(report["per_class"]) == 8
    assert report["per_class"][1]["precision"] is None
    assert report["confusion_examples"][0]["count"] == 1
    assert report["accuracy_acceptance"] == "not_defined_not_claimed"
    metrics.box.p[0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        evaluate.metrics_report(metrics, validator, evaluate.source_names())
    metrics.names = list(reversed(evaluate.source_names()))
    with pytest.raises(ValueError, match="class names"):
        evaluate.metrics_report(metrics, validator, evaluate.source_names())


def test_cleanup_is_scoped_dry_run_and_requires_successful_current_validation(config):
    value, root = config
    dataset = root / "Dataset"
    run = dataset / "runs" / value["run_name"]
    (run / "weights").mkdir(parents=True)
    for filename in ("best.pt", "last.pt", "resume-latest.pt", "resume-previous.pt"):
        (run / "weights" / filename).write_bytes(filename.encode())
    labels = dataset / "prepared" / "labels"
    labels.mkdir()
    (labels / "train.cache").write_bytes(b"redundant")
    (labels / "train.txt").write_text("real label")
    raw = dataset / "raw"
    raw.mkdir()
    (raw / "train.cache").write_bytes(b"raw must survive")
    report = {"split": "val", "numerical_validation_passed": True,
              "weights_sha256": checkpointing.sha256_file(run / "weights" / "best.pt"),
              "dataset_manifest_sha256": checkpointing.sha256_file(dataset / "prepared" / "manifest.jsonl")}
    path = run / "evaluation-val.json"
    checkpointing.write_json(path, report)
    checkpointing.write_json(run / "run_status.json", {"status": "evaluated"})
    assert evaluate.cleanup_caches(dataset, path)["bytes"] == 9
    assert (labels / "train.cache").exists()
    evaluate.cleanup_caches(dataset, path, apply=True)
    assert not (labels / "train.cache").exists()
    assert (labels / "train.txt").exists() and (raw / "train.cache").exists()
    assert len(list((run / "weights").glob("*.pt"))) == 4
    report["numerical_validation_passed"] = False
    checkpointing.write_json(path, report)
    with pytest.raises(ValueError, match="Successful validation"):
        evaluate.cleanup_caches(dataset, path, apply=True)


def test_cleanup_rejects_hash_changed_since_validation(config):
    value, root = config
    dataset = root / "Dataset"
    run = dataset / "runs" / value["run_name"]
    (run / "weights").mkdir(parents=True)
    (run / "weights" / "best.pt").write_bytes(b"changed")
    report = run / "evaluation-val.json"
    checkpointing.write_json(report, {"split": "val", "numerical_validation_passed": True, "weights_sha256": "old"})
    with pytest.raises(ValueError, match="Successful validation"):
        evaluate.cleanup_caches(dataset, report, apply=True)


def test_model_injected_evaluation_exports_manifest_only_after_callback_and_preserves_test_split(config):
    value, root = config
    dataset = root / "Dataset"
    run = dataset / "runs" / value["run_name"]
    (run / "weights").mkdir(parents=True)
    (run / "weights" / "best.pt").write_bytes(b"fake trained weights")
    identity = {"manifest_sha256": checkpointing.sha256_file(dataset / "prepared" / "manifest.jsonl"),
                "data_yaml_sha256": checkpointing.sha256_file(dataset / "prepared" / "data.yaml"),
                "config_sha256": checkpointing.fingerprint(value)}
    checkpointing.write_json(run / "run_metadata.json", {"identity": identity})
    checkpointing.write_json(run / "run_status.json", {"status": "training_completed_pending_evaluation"})
    calls = []

    class FakeModel:
        def __init__(self, weights):
            assert Path(weights).is_file()
        def add_callback(self, event, callback):
            assert event == "on_val_end"
            self.callback = callback
        def val(self, **kwargs):
            calls.append(kwargs)
            metrics, validator = fake_metrics()
            self.callback(validator)
            return metrics

    evaluate.evaluate(value, "val", model_factory=FakeModel)
    manifest = json.loads((run / "model_manifest.json").read_text())
    assert manifest["source_class_names"] == evaluate.source_names()
    assert manifest["status"] == "experimental"
    assert manifest["weights_path"].startswith("Dataset/runs/")
    manifest_before = (run / "model_manifest.json").read_bytes()
    report = evaluate.evaluate(value, "test", model_factory=FakeModel)
    assert json.loads(report.read_text())["split_role"] == "held_out_test_no_threshold_tuning"
    assert (run / "model_manifest.json").read_bytes() == manifest_before
    assert calls[0]["conf"] == calls[1]["conf"] == 0.001
    changed = copy.deepcopy(value)
    changed["inference"]["conf"] = 0.4
    with pytest.raises(ValueError, match="config"):
        evaluate.evaluate(changed, "test", model_factory=FakeModel)


@pytest.fixture
def smoke_source(tmp_path, monkeypatch):
    monkeypatch.setattr(make_smoke, "ROOT", tmp_path)
    module = tmp_path / "SystemCode" / "model"
    module.mkdir(parents=True)
    for filename in ("label_schema.json", "training.example.json"):
        (module / filename).write_bytes(Path(train.__file__).with_name(filename).read_bytes())
    prepared = tmp_path / "Dataset" / "prepared"
    prepared.mkdir(parents=True)
    checkpointing.write_json(prepared / "audit.json", {"status": "passed_full_content_validation"})
    records = []
    for split in ("train", "val", "test"):
        for class_id in range(8):
            row = {"sample_id": f"{split}-{class_id}", "group_id": f"group-{split}-{class_id}",
                   "split": split, "assigned_split": split, "is_mirror": False,
                   "boxes": [[class_id, 0.5, 0.5, 0.2, 0.2]]}
            records.append(row)
            # Test files deliberately do not exist: selection must never attempt to read them.
            if split != "test":
                for kind, extension in (("images", ".jpg"), ("labels", ".txt")):
                    directory = prepared / kind / split
                    directory.mkdir(parents=True, exist_ok=True)
                    (directory / (row["sample_id"] + extension)).write_bytes(row["sample_id"].encode())
    # A source mirror belongs to the frozen val group but is excluded from val image materialization.
    records.append({"sample_id": "xmirror_val-0", "group_id": "group-val-0", "split": None,
                    "assigned_split": "val", "is_mirror": True, "boxes": [[0, 0.5, 0.5, 0.2, 0.2]]})
    (prepared / "manifest.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    return tmp_path, records


def test_smoke_preserves_frozen_train_val_groups_and_never_reads_test_or_excluded_mirrors(smoke_source):
    root, original = smoke_source
    config_path = make_smoke.prepare_smoke()
    smoke = root / "Dataset" / "smoke"
    selected = [json.loads(line) for line in (smoke / "manifest.jsonl").read_text().splitlines()]
    source_by_id = {row["sample_id"]: row for row in original}
    assert len(selected) == 16
    assert all(row == source_by_id[row["sample_id"]] and row["split"] in {"train", "val"} for row in selected)
    groups = {split: {row["group_id"] for row in selected if row["split"] == split} for split in ("train", "val")}
    assert not groups["train"] & groups["val"]
    assert all("test" not in row["sample_id"] and not row["is_mirror"] for row in selected)
    for split in ("train", "val"):
        assert {box[0] for row in selected if row["split"] == split for box in row["boxes"]} == set(range(8))
        assert len(list((smoke / "images" / split).glob("*.jpg"))) == 8
    assert not (smoke / "images" / "test").exists()
    result = json.loads(config_path.read_text())
    assert result["train"]["epochs"] == 2 and result["train"]["workers"] == 0
    assert result["data"] == "Dataset/smoke/data.yaml"


@pytest.mark.parametrize("existing", ["directory", "configuration"])
def test_smoke_refuses_to_overwrite_existing_outputs(smoke_source, existing):
    root, _ = smoke_source
    if existing == "directory":
        folder = root / "Dataset" / "smoke"
        folder.mkdir()
        sentinel = folder / "manifest.jsonl"
    else:
        sentinel = root / "Dataset" / "smoke-config.json"
    original_content = b"existing output must survive byte-for-byte"
    sentinel.write_bytes(original_content)
    with pytest.raises((ValueError, FileExistsError)):
        make_smoke.prepare_smoke()
    assert sentinel.read_bytes() == original_content


@pytest.fixture
def yaml_config(tmp_path):
    value = json.loads(Path(train.__file__).with_name("training.example.json").read_text())
    dataset = tmp_path / "Dataset"
    prepared = dataset / "prepared"
    for split in ("train", "val", "test"):
        (prepared / "images" / split).mkdir(parents=True)
    (prepared / "manifest.jsonl").write_text("{}\n")
    (dataset / "pretrained").mkdir()
    (dataset / "pretrained" / "yolo11n.pt").write_bytes(b"test local weight")
    fields = {"path": str(prepared), "train": "images/train", "val": "images/val", "test": "images/test",
              "nc": 8, "names": evaluate.source_names()}
    yaml_path = prepared / "data.yaml"
    config_path = dataset / "config.json"

    def save(changed_fields=None, changed_config=None, extra=""):
        yaml_path.write_text("".join(f"{key}: {json.dumps(item)}\n" for key, item in (changed_fields or fields).items()) + extra)
        checkpointing.write_json(config_path, changed_config or value)
        return train.load_config(config_path, tmp_path)

    return tmp_path, fields, value, save


@pytest.mark.parametrize("layout", ["prepared", "omitted_path", "directory_list", "smoke_without_test"])
def test_yaml_validation_accepts_generated_local_layouts(yaml_config, layout):
    _, fields, value, save = yaml_config
    changed = copy.deepcopy(fields)
    if layout == "omitted_path":
        del changed["path"]
    elif layout == "directory_list":
        changed["train"] = ["images/train"]
    elif layout == "smoke_without_test":
        del changed["test"]
    assert save(changed) == value


def test_config_rejects_non_dataset_repository_folder(yaml_config):
    _, _, value, save = yaml_config
    changed = copy.deepcopy(value)
    changed["dataset_root"] = "SystemCode"
    with pytest.raises(ValueError, match="Dataset subtree"):
        save(changed_config=changed)


@pytest.mark.parametrize("field", ["path", "train", "val", "test", "train_list"])
def test_yaml_rejects_resolved_absolute_and_relative_path_escapes(yaml_config, field):
    root, fields, _, save = yaml_config
    outside = root / "outside"
    outside.mkdir()
    changed = copy.deepcopy(fields)
    if field == "path":
        changed["path"] = str(outside)
    elif field == "train_list":
        changed["train"] = ["images/train", str(outside)]
    elif field == "test":
        changed["test"] = "../../outside"
    else:
        changed[field] = str(outside)
    with pytest.raises(ValueError, match="escapes dataset_root"):
        save(changed)


def test_yaml_rejects_download_directive_before_any_execution(yaml_config):
    root, _, _, save = yaml_config
    sentinel = root / "must-not-be-created"
    with pytest.raises(ValueError, match="download directives"):
        save(extra=f'download: "touch {sentinel}"\n')
    assert not sentinel.exists()


def test_yaml_rejects_relative_global_path_duplicate_keys_and_image_lists(yaml_config):
    root, fields, _, save = yaml_config
    changed = copy.deepcopy(fields)
    changed["path"] = "Dataset/prepared"
    with pytest.raises(ValueError, match="absolute local"):
        save(changed)
    with pytest.raises(ValueError, match="duplicate"):
        save(extra=f'path: {json.dumps(fields["path"])}\n')
    images_list = root / "Dataset" / "prepared" / "images.txt"
    images_list.write_text(str(root / "outside.jpg"))
    changed = copy.deepcopy(fields)
    changed["train"] = "images.txt"
    with pytest.raises(ValueError, match="existing image directory"):
        save(changed)


@pytest.mark.parametrize("epochs,patience,imgsz,batch", [(30, 10, 640, 16), (60, 60, 960, 32), (40, 20, 832, 64), (1, 1, 32, 1)])
def test_config_accepts_bounded_high_resolution_and_existing_training_recipes(yaml_config, epochs, patience, imgsz, batch):
    _, _, value, save = yaml_config
    changed = copy.deepcopy(value)
    changed["train"].update(epochs=epochs, patience=patience, imgsz=imgsz, batch=batch)
    changed["inference"]["imgsz"] = imgsz
    assert save(changed_config=changed) == changed


@pytest.mark.parametrize("field,item", [("epochs", 61), ("epochs", 0), ("patience", 61), ("patience", 0),
                                      ("imgsz", 992), ("imgsz", 31), ("imgsz", 641), ("imgsz", 959),
                                      ("batch", 65), ("epochs", True), ("patience", True), ("batch", True),
                                      ("imgsz", True), ("workers", False), ("seed", True),
                                      ("epochs", 30.0), ("imgsz", 960.0), ("fliplr", False)])
def test_config_rejects_excessive_rounded_or_boolean_integer_training_values(yaml_config, field, item):
    _, _, value, save = yaml_config
    changed = copy.deepcopy(value)
    changed["train"][field] = item
    if field == "imgsz":
        changed["inference"]["imgsz"] = item
    with pytest.raises(ValueError):
        save(changed_config=changed)


@pytest.mark.parametrize("field,item", [("conf", True), ("iou", False), ("imgsz", 640.0), ("conf", "0.25"), ("conf", float("inf"))])
def test_config_rejects_wrong_inference_parameter_types(yaml_config, field, item):
    _, _, value, save = yaml_config
    changed = copy.deepcopy(value)
    changed["inference"][field] = item
    with pytest.raises(ValueError):
        save(changed_config=changed)


@pytest.mark.parametrize("field", ["resume", "model", "classes", "single_cls", "fraction"])
def test_high_resolution_recipe_preserves_runner_owned_overrides(yaml_config, field):
    _, _, value, save = yaml_config
    changed = copy.deepcopy(value)
    changed["train"].update(epochs=60, patience=60, imgsz=960)
    changed["inference"]["imgsz"] = 960
    changed["train"][field] = False
    with pytest.raises(ValueError, match="Runner-owned"):
        save(changed_config=changed)


def test_config_accepts_existing_best_checkpoint_for_a_separate_fine_tune_run(yaml_config):
    root, _, value, save = yaml_config
    parent = root / "Dataset/runs/parent-completed/weights/best.pt"
    parent.parent.mkdir(parents=True)
    parent.write_bytes(b"eight-class parent checkpoint")
    changed = copy.deepcopy(value)
    changed.update(model="Dataset/runs/parent-completed/weights/best.pt", run_name="new-finetune",
                   model_version="yolo11s-rdd2022es-finetune-experimental")
    changed["train"].update(epochs=60, patience=60, imgsz=960)
    changed["inference"]["imgsz"] = 960
    assert save(changed_config=changed) == changed
    assert parent.read_bytes() == b"eight-class parent checkpoint"


def test_new_run_fine_tune_initializes_parent_weights_without_resume_or_replacing_parent(config):
    value, root = config
    parent = root / "Dataset/runs/completed-parent/weights/best.pt"
    parent.parent.mkdir(parents=True)
    parent.write_bytes(b"trained eight-class parent")
    value.update(model="Dataset/runs/completed-parent/weights/best.pt", run_name="new-finetune")
    calls = []

    class FakeModel:
        def __init__(self, path):
            calls.append(Path(path))
        def add_callback(self, event, callback):
            pass
        def train(self, **arguments):
            assert "resume" not in arguments
            assert arguments["name"] == "new-finetune"

    run = train.run_training(value, model_factory=FakeModel, runtime={"python": "fake", "packages": {}})
    metadata = json.loads((run / "run_metadata.json").read_text())
    assert calls == [parent]
    assert metadata["resume_history"] == []
    assert metadata["identity"]["pretrained_sha256"] == checkpointing.sha256_file(parent)
    assert parent.read_bytes() == b"trained eight-class parent"
    assert json.loads((run / "run_status.json").read_text())["status"] == "training_completed_pending_evaluation"
