"""Generated local ZIPs exercise fail-closed content validation and splits."""

from io import BytesIO
import importlib.util
import json
from pathlib import Path
import random
import stat
import zipfile

from PIL import Image, ImageOps
import pytest


SPEC = importlib.util.spec_from_file_location(
    "roadguard_data_pipeline", Path(__file__).parents[1] / "model" / "data_pipeline.py"
)
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


def jpeg(image):
    output = BytesIO()
    image.save(output, format="JPEG", quality=100, subsampling=0)
    return output.getvalue()


def make_archive(root, count=12, changes=None):
    root.mkdir(parents=True, exist_ok=True)
    files = {"classes.txt": "\n".join(
        row["source_name"] for row in json.loads(pipeline.SCHEMA_PATH.read_text(encoding="utf-8"))["classes"]
    ).encode()}
    for index in range(count):
        country = pipeline.COUNTRIES[index % 4]
        name = f"{country}_{index:06}"
        rng = random.Random(index)
        image = Image.new("RGB", (32, 32))
        image.putdata([tuple(rng.randrange(256) for _ in range(3)) for _ in range(1024)])
        # Different mean colours prevent unrelated dHash candidates being joined.
        image = Image.blend(image, Image.new("RGB", (32, 32), tuple(rng.randrange(256) for _ in range(3))), 0.5)
        files[f"{name}.jpg"] = jpeg(image)
        files[f"xmirror_{name}.jpg"] = jpeg(ImageOps.mirror(image))
        files[f"{name}.txt"] = b"0 0.25 0.5 0.2 0.2\n" if index % 2 else b""
        files[f"xmirror_{name}.txt"] = b"0 0.75 0.5 0.2 0.2\n" if index % 2 else b""
    if changes:
        changes(files)
    archive = root / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name, data in files.items():
            if data is not None:
                output.writestr(f"combined_annotatedv2/{name}", data)
    return archive


def records(root):
    return [json.loads(line) for line in (root / "prepared/manifest.jsonl").read_text(encoding="utf-8").splitlines()]


def test_split_reproducible_groups_disjoint_original_eval_and_yaml(tmp_path):
    summaries, manifests = [], []
    for folder in ("one", "two"):
        root = tmp_path / folder
        archive = make_archive(root, 40)
        summaries.append(pipeline.prepare(archive, root, strict_inventory=False))
        manifests.append(records(root))
    assert summaries[0] == summaries[1]
    assert [(r["sample_id"], r["split"], r["group_id"]) for r in manifests[0]] == [
        (r["sample_id"], r["split"], r["group_id"]) for r in manifests[1]
    ]
    group_splits = {}
    for sample in manifests[0]:
        group_splits.setdefault(sample["group_id"], set()).add(sample["assigned_split"])
        if sample["split"] in ("val", "test"):
            assert not sample["is_mirror"]
    assert all(len(values) == 1 for values in group_splits.values())
    assert sum(summaries[0]["splits"][s]["groups"] for s in ("train", "val", "test")) == 40
    yaml_text = (tmp_path / "one/prepared/data.yaml").read_text(encoding="utf-8")
    assert json.loads(yaml_text.split("names: ")[1]) == [
        row["source_name"] for row in json.loads(pipeline.SCHEMA_PATH.read_text(encoding="utf-8"))["classes"]
    ]
    audit = json.loads((tmp_path / "one/prepared/audit.json").read_text(encoding="utf-8"))
    assert audit["full_decode_attempts"] == 80
    assert audit["grouped_leakage_assertions"] == "passed"
    assert "not proof" in audit["empty_annotation_interpretation"]


def test_documented_missing_label_group_quarantined_and_orphan_recorded(tmp_path):
    def changes(files):
        for prefix in ("", "xmirror_"):
            files[f"{prefix}Czech_001003.jpg"] = files[f"{prefix}Czech_000000.jpg"]
        files["India_001032.txt"] = b""
    archive = make_archive(tmp_path, changes=changes)
    pipeline.prepare(archive, tmp_path, strict_inventory=False)
    excluded = [r for r in records(tmp_path) if "001003" in r["sample_id"]]
    assert len(excluded) == 2
    assert all(r["exclusion_reason"] == "quarantined_missing_label_group" and r["split"] is None for r in excluded)
    audit = json.loads((tmp_path / "prepared/audit.json").read_text(encoding="utf-8"))
    assert audit["exclusions"][0]["exclusion_reason"] == "documented_orphan_label"
    assert (tmp_path / "raw/rdd2022es-v1/combined_annotatedv2/India_001032.txt").exists()


@pytest.mark.parametrize("label", [b"0 0.9 0.5 0.4 0.2", b"8 0.5 0.5 0.2 0.2", b"0 nan 0.5 0.2 0.2", b"0 0.5 0.5 0 0.2", b"1.0 0.5 0.5 0.2 0.2"])
def test_invalid_labels_fail_before_publishing_training_yaml(tmp_path, label):
    archive = make_archive(tmp_path, changes=lambda files: files.update({"India_000001.txt": label}))
    with pytest.raises(pipeline.PreparationError, match="Full validation failed"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    audit = json.loads((tmp_path / "prepared/audit.json").read_text(encoding="utf-8"))
    assert audit["errors"] and audit["status"] == "failed_validation"
    assert not (tmp_path / "prepared/data.yaml").exists()


def test_unexpected_missing_label_fails_instead_of_becoming_negative(tmp_path):
    archive = make_archive(tmp_path, changes=lambda files: files.update({"India_000001.txt": None}))
    with pytest.raises(pipeline.PreparationError, match="Full validation failed"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    assert any("unexpected missing label" in message for message in json.loads(
        (tmp_path / "prepared/audit.json").read_text(encoding="utf-8")
    )["errors"])


@pytest.mark.parametrize("member", ["../escaped.txt", "/escaped.txt", "combined_annotatedv2/../escaped.txt", "combined_annotatedv2/./Czech_1.jpg", "combined_annotatedv2//Czech_1.jpg", "combined_annotatedv2/Czech_1.jpg:stream"])
def test_archive_traversal_rejected_before_any_member_written(tmp_path, member):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("combined_annotatedv2/Czech_1.jpg", b"first")
        output.writestr(member, b"bad")
    with pytest.raises(pipeline.PreparationError):
        pipeline.safe_extract(archive, tmp_path / "raw", "fixture-hash")
    assert not list((tmp_path / "raw").rglob("*.jpg"))


def test_archive_symlink_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    info = zipfile.ZipInfo("combined_annotatedv2/Czech_1.jpg")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(info, "outside")
    with pytest.raises(pipeline.PreparationError, match="Unsafe archive member"):
        pipeline.safe_extract(archive, tmp_path / "raw", "fixture-hash")


def test_exact_duplicate_different_country_cannot_cross_split(tmp_path):
    def changes(files):
        for prefix in ("", "xmirror_"):
            files[f"{prefix}India_000001.jpg"] = files[f"{prefix}Czech_000000.jpg"]
            files[f"{prefix}India_000001.txt"] = b""
    archive = make_archive(tmp_path, changes=changes)
    pipeline.prepare(archive, tmp_path, strict_inventory=False)
    selected = [r for r in records(tmp_path) if r["original_group"] in ("Czech_000000", "India_000001")]
    assert len({r["group_id"] for r in selected}) == 1
    assert len({r["assigned_split"] for r in selected}) == 1


def test_near_duplicate_mirror_candidates_group_before_split(tmp_path):
    def changes(files):
        with Image.open(BytesIO(files["Czech_000000.jpg"])) as image:
            original = ImageOps.mirror(image).convert("RGB")
            original.putpixel((0, 0), original.getpixel((1, 0)))
            files["India_000001.jpg"] = jpeg(original)
            files["xmirror_India_000001.jpg"] = jpeg(ImageOps.mirror(original))
        files["India_000001.txt"] = files["xmirror_India_000001.txt"] = b""
    archive = make_archive(tmp_path, changes=changes)
    pipeline.prepare(archive, tmp_path, strict_inventory=False)
    selected = [r for r in records(tmp_path) if r["original_group"] in ("Czech_000000", "India_000001")]
    assert len({r["group_id"] for r in selected}) == 1
    audit = json.loads((tmp_path / "prepared/audit.json").read_text(encoding="utf-8"))
    assert audit["duplicate_grouping"]["near_group_links"] >= 1


def test_raw_resume_rejects_mutation_and_prepared_is_not_overwritten(tmp_path):
    archive = make_archive(tmp_path)
    pipeline.prepare(archive, tmp_path, strict_inventory=False)
    with pytest.raises(pipeline.PreparationError, match="already exists"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    destination = tmp_path / "raw/rdd2022es-v1"
    (destination / "combined_annotatedv2/classes.txt").write_text("modified")
    with pytest.raises(pipeline.PreparationError, match="differs from archive"):
        pipeline.safe_extract(archive, destination, pipeline.sha256_file(archive))


def test_corrupt_image_and_mismatched_mirror_fail(tmp_path):
    archive = make_archive(tmp_path, changes=lambda files: files.update({"Czech_000000.jpg": b"not a jpeg"}))
    with pytest.raises(pipeline.PreparationError, match="Full validation failed"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    assert not (tmp_path / "prepared/data.yaml").exists()


def test_copy_fallback_preserves_content(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_bytes(b"image-content")
    def denied(*args):
        raise OSError("filesystem does not support hardlinks")
    monkeypatch.setattr(pipeline.os, "link", denied)
    assert pipeline.link_or_copy(source, target) == "copy"
    assert target.read_bytes() == source.read_bytes()


def test_wrong_source_classes_and_wrong_pinned_archive_fail(tmp_path):
    archive = make_archive(tmp_path, changes=lambda files: files.update({"classes.txt": b"wrong classes"}))
    with pytest.raises(pipeline.PreparationError, match="SHA-256/size"):
        pipeline.prepare(archive, tmp_path)
    with pytest.raises(pipeline.PreparationError, match="classes.txt"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    assert not (tmp_path / "prepared/data.yaml").exists()


def oriented_jpeg(encoded, orientation):
    with Image.open(BytesIO(encoded)) as source:
        image = source.convert("RGB")
        exif = Image.Exif()
        exif[274] = orientation
        output = BytesIO()
        image.save(output, format="JPEG", quality=100, subsampling=0, exif=exif)
        return output.getvalue()


def test_known_exif_orientation_quarantines_whole_validated_group(tmp_path, monkeypatch):
    observations = {}
    def changes(files):
        files["India_000001.jpg"] = oriented_jpeg(files["India_000001.jpg"], 8)
        observations["India_000001"] = {
            "original_sha256": pipeline.hashlib.sha256(files["India_000001.jpg"]).hexdigest(),
            "original_orientation": 8,
            "mirror_sha256": pipeline.hashlib.sha256(files["xmirror_India_000001.jpg"]).hexdigest(),
            "mirror_orientation": 1,
        }
    archive = make_archive(tmp_path, changes=changes)
    monkeypatch.setattr(pipeline, "KNOWN_EXIF_QUARANTINE", observations)
    pipeline.prepare(archive, tmp_path, strict_inventory=False)
    selected = [r for r in records(tmp_path) if r["original_group"] == "India_000001"]
    assert len(selected) == 2
    assert {r["exif_orientation"] for r in selected} == {1, 8}
    assert all(r["exclusion_reason"] == "exif_orientation_unverified_labels" and r["split"] is None for r in selected)
    assert all(r["boxes"] for r in selected)  # Labels still get fully validated.
    audit = json.loads((tmp_path / "prepared/audit.json").read_text(encoding="utf-8"))
    assert audit["quarantined_groups"] == ["India_000001"]
    assert audit["image_exclusion_counts"]["exif_orientation_unverified_labels"] == 2
    assert audit["full_decode_attempts"] == 24 and not audit["errors"]


def test_unexpected_exif_orientation_remains_fatal(tmp_path):
    def changes(files):
        files["India_000001.jpg"] = oriented_jpeg(files["India_000001.jpg"], 3)
    archive = make_archive(tmp_path, changes=changes)
    with pytest.raises(pipeline.PreparationError, match="Full validation failed"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    audit = json.loads((tmp_path / "prepared/audit.json").read_text(encoding="utf-8"))
    assert any("EXIF orientation 3" in error for error in audit["errors"])
    assert not (tmp_path / "prepared/data.yaml").exists()


def test_known_exif_exception_requires_matching_member_hash(tmp_path, monkeypatch):
    def changes(files):
        files["India_000001.jpg"] = oriented_jpeg(files["India_000001.jpg"], 8)
    archive = make_archive(tmp_path, changes=changes)
    monkeypatch.setattr(pipeline, "KNOWN_EXIF_QUARANTINE", {"India_000001": {
        "original_sha256": "0" * 64, "original_orientation": 8,
        "mirror_sha256": "0" * 64, "mirror_orientation": 1,
    }})
    with pytest.raises(pipeline.PreparationError, match="Full validation failed"):
        pipeline.prepare(archive, tmp_path, strict_inventory=False)
    audit = json.loads((tmp_path / "prepared/audit.json").read_text(encoding="utf-8"))
    assert any("quarantine member SHA-256 differs" in error for error in audit["errors"])
    assert not (tmp_path / "prepared/data.yaml").exists()
