"""Local, fail-closed preparation of juusos/rdd2022es version 1.

No network access. Raw files are preserved; prepared files must be treated as
read-only because hardlinks share the raw inode. See data_readme.md.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import stat
import sys
import zipfile

from PIL import Image, ImageOps


DATASET_REF = "juusos/rdd2022es"
DATASET_VERSION = 1
PINNED_ARCHIVE_BYTES = 2_611_933_018
PINNED_ARCHIVE_SHA256 = "3ceb9de3b7ca7083379e4fc62748bafcda0a82d1baf4627cf87891c9595fa775"
COUNTRIES = ("Czech", "India", "Japan", "United_States")
KNOWN_MISSING_LABELS = {"Czech_001003", "xmirror_Czech_001003"}
KNOWN_ORPHAN_LABELS = {"India_001032"}
# Full v1 decode on 2026-10-13 found two original images with EXIF rotations.
# Their labels' coordinate convention is unverified; exclude both whole groups.
# Exact member SHA and orientation checks keep this an explicit exception rather
# than permission to ignore unexpected source errors.
KNOWN_EXIF_QUARANTINE = {
    "India_000430": {
        "original_sha256": "01c4ef927c8193a209e1169f8bc937ad16764c1b2d756ba0a5c9d7332ea3fa9c",
        "original_orientation": 8,
        "mirror_sha256": "c4bfebccb2f4a6bda5a9891c18d6a2bcc43689395e2a634cd1c118ae15c6c167",
        "mirror_orientation": 1,
    },
    "India_004098": {
        "original_sha256": "219984707789be5cab1418ae6804227487b08b1eae5b158cf88dc44b26e73c2a",
        "original_orientation": 3,
        "mirror_sha256": "b3f2acdf5013819d14f6b9f503a3dfa2ae155eddee6b36aa0424e8d48f9feb35",
        "mirror_orientation": 1,
    },
}
NAME = re.compile(r"^(xmirror_)?(Czech|India|Japan|United_States)_[0-9]+$")
SCHEMA_PATH = Path(__file__).with_name("label_schema.json")


class PreparationError(ValueError):
    """Invalid source data or an unsafe preparation request."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def checked_child(root: Path, path: Path) -> Path:
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise PreparationError(f"Unsafe path: {path}")
    return path


def safe_extract(archive: Path, destination: Path, archive_sha256: str) -> list[str]:
    """Preflight all members before extraction; reject links and path aliases.

An existing extraction is rechecked against ZIP CRCs, never silently trusted.
"""
    destination = checked_child(destination.parent, destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        names, seen = [], set()
        for member in source.infolist():
            name = member.filename
            parts = PurePosixPath(name).parts
            spelling_parts = name.rstrip("/").split("/")
            mode = member.external_attr >> 16
            if (not parts or "\\" in name or ":" in name or name.startswith("/")
                    or any(part in ("", "..", ".") or part.endswith((" ", ".")) for part in spelling_parts)
                    or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise PreparationError(f"Unsafe archive member: {name}")
            if parts[0] != "combined_annotatedv2" or len(parts) > 2:
                raise PreparationError(f"Unexpected archive layout: {name}")
            if member.is_dir():
                if len(parts) != 1:
                    raise PreparationError(f"Unexpected archive directory: {name}")
                continue
            if len(parts) != 2 or name.casefold() in seen:
                raise PreparationError(f"Duplicate or invalid archive member: {name}")
            seen.add(name.casefold())
            leaf = PurePosixPath(name)
            if leaf.name != "classes.txt" and (leaf.suffix != ".jpg" and leaf.suffix != ".txt"):
                raise PreparationError(f"Unexpected file type: {name}")
            if leaf.name != "classes.txt" and not NAME.fullmatch(leaf.stem):
                raise PreparationError(f"Unexpected source filename: {name}")
            names.append(name)
        expected = set(names)
        existing = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
        if existing - expected - {"extraction.json"}:
            raise PreparationError("Raw directory contains files outside this archive")
        for member in source.infolist():
            if member.is_dir():
                continue
            target = checked_child(destination, destination / member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            checked_child(destination, target.parent)
            # CRC is checked by ZipExtFile at EOF. Compare existing bytes to the
            # archive stream as well, so resume cannot use a modified raw file.
            with source.open(member) as incoming:
                if target.exists():
                    with target.open("rb") as current:
                        while True:
                            block = incoming.read(1024 * 1024)
                            if current.read(len(block)) != block or (not block and current.read(1)):
                                raise PreparationError(f"Existing raw file differs from archive: {target.name}")
                            if not block:
                                break
                else:
                    with target.open("xb") as output:
                        shutil.copyfileobj(incoming, output)
        write_json(destination / "extraction.json", {"archive_sha256": archive_sha256, "files": len(names)})
    return sorted(names)


def parse_labels(path: Path, class_count: int = 8) -> list[list[float | int]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) != 5 or not re.fullmatch(r"[0-9]+", parts[0]):
            raise PreparationError(f"{path.name}:{number}: expected integer class and four coordinates")
        class_id = int(parts[0])
        try:
            x, y, width, height = map(float, parts[1:])
        except ValueError as error:
            raise PreparationError(f"{path.name}:{number}: invalid numeric coordinate") from error
        if class_id not in range(class_count):
            raise PreparationError(f"{path.name}:{number}: invalid class ID {class_id}")
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            raise PreparationError(f"{path.name}:{number}: non-finite coordinate")
        # Six-decimal publisher rounding can move an edge by half a micro-unit.
        tolerance = 1e-6
        if (not 0 <= x <= 1 or not 0 <= y <= 1 or not 0 < width <= 1 or not 0 < height <= 1
                or x - width / 2 < -tolerance or x + width / 2 > 1 + tolerance
                or y - height / 2 < -tolerance or y + height / 2 > 1 + tolerance):
            raise PreparationError(f"{path.name}:{number}: box outside normalized image bounds")
        rows.append([class_id, x, y, width, height])
    return rows


def image_fingerprints(path: Path, expected_orientation: int = 1) -> tuple[int, int, str, tuple[int, int], bytes, bytes, int]:
    with Image.open(path) as image:
        if image.format != "JPEG" or getattr(image, "n_frames", 1) != 1:
            raise PreparationError(f"{path.name}: source image must be a single JPEG")
        image.load()  # Full decode, not header-only verification.
        orientation = image.getexif().get(274, 1)
        if orientation != expected_orientation:
            raise PreparationError(f"{path.name}: EXIF orientation {orientation} differs from expected {expected_orientation}; labels require review")
        rgb = image.convert("RGB")
        pixel_hash = hashlib.sha256(f"{rgb.width}x{rgb.height}:".encode() + rgb.tobytes()).hexdigest()
        hashes, thumbs = [], []
        for view in (rgb, ImageOps.mirror(rgb)):
            gray = view.convert("L").resize((9, 8), Image.Resampling.LANCZOS).tobytes()
            value = 0
            for row in range(8):
                for col in range(8):
                    value = (value << 1) | (gray[row * 9 + col] > gray[row * 9 + col + 1])
            hashes.append(value)
            thumbs.append(view.resize((16, 16), Image.Resampling.LANCZOS).tobytes())
        return hashes[0], hashes[1], pixel_hash, rgb.size, thumbs[0], thumbs[1], orientation


class Groups:
    def __init__(self, identifiers: list[str]):
        self.parent = {key: key for key in identifiers}

    def find(self, key: str) -> str:
        if self.parent[key] != key:
            self.parent[key] = self.find(self.parent[key])
        return self.parent[key]

    def union(self, left: str, right: str) -> None:
        a, b = sorted((self.find(left), self.find(right)))
        self.parent[b] = a


class BKTree:
    """Hamming-distance index; avoids unconditional all-pairs comparisons."""
    def __init__(self):
        self.root = None

    def add(self, value: int, identifier: str, orientation: int) -> None:
        if self.root is None:
            self.root = [value, [(identifier, orientation)], {}]
            return
        node = self.root
        while True:
            distance = (node[0] ^ value).bit_count()
            if distance == 0:
                node[1].append((identifier, orientation))
                return
            if distance not in node[2]:
                node[2][distance] = [value, [(identifier, orientation)], {}]
                return
            node = node[2][distance]

    def query(self, value: int, radius: int):
        pending = [self.root] if self.root is not None else []
        while pending:
            node = pending.pop()
            distance = (node[0] ^ value).bit_count()
            if distance <= radius:
                yield from node[1]
            pending.extend(child for edge, child in node[2].items() if distance - radius <= edge <= distance + radius)


def group_duplicates(samples: list[dict], fingerprints: dict, radius: int, max_rmse: float) -> tuple[Groups, dict]:
    groups = Groups([sample["sample_id"] for sample in samples])
    seen_sha, seen_pixels, known = {}, {}, {}
    stats = {"exact_byte_links": 0, "exact_pixel_links": 0, "near_candidate_comparisons": 0,
             "near_group_links": 0, "near_links": [], "dhash_radius": radius, "thumbnail_rmse_max": max_rmse}
    for sample in samples:
        key = sample["sample_id"]
        original = sample["original_group"]
        if original in known:
            groups.union(key, known[original])
        known[original] = key
        for value, index, counter in ((sample["image_sha256"], seen_sha, "exact_byte_links"),
                                       (fingerprints[key][2], seen_pixels, "exact_pixel_links")):
            if value in index:
                groups.union(key, index[value])
                stats[counter] += 1
            else:
                index[value] = key
    tree = BKTree()
    # Original/mirror pair content is separately validated. One original per
    # exact component is enough here; the source mirrors must not inflate counts.
    representatives = {}
    for sample in samples:
        if not sample["is_mirror"]:
            representatives.setdefault(groups.find(sample["sample_id"]), sample["sample_id"])
    for key in sorted(representatives.values()):
        fingerprint = fingerprints[key]
        for other, orientation in tree.query(fingerprint[0], radius):
            stats["near_candidate_comparisons"] += 1
            thumbnail = fingerprints[other][4 + orientation]
            rmse = math.sqrt(sum((a - b) ** 2 for a, b in zip(fingerprint[4], thumbnail)) / len(thumbnail))
            if rmse <= max_rmse and groups.find(key) != groups.find(other):
                groups.union(key, other)
                stats["near_group_links"] += 1
                stats["near_links"].append({"left": key, "right": other, "mirror": bool(orientation),
                                            "dhash_distance": (fingerprint[0] ^ fingerprints[other][orientation]).bit_count(),
                                            "rmse": rmse})
        tree.add(fingerprint[0], key, 0)
        tree.add(fingerprint[1], key, 1)
    return groups, stats


def assign_splits(samples: list[dict], groups: Groups, seed: int) -> dict[str, str]:
    countries = defaultdict(set)
    for sample in samples:
        countries[groups.find(sample["sample_id"])].add(sample["country"])
    strata = defaultdict(list)
    for group, values in countries.items():
        strata[tuple(sorted(values))].append(group)
    assignments = {}
    generator = random.Random(seed)
    for stratum in sorted(strata):
        identifiers = sorted(strata[stratum])
        generator.shuffle(identifiers)
        total = len(identifiers)
        # Largest-remainder apportionment: ratios apply to independent groups.
        exact = [total * value for value in (0.70, 0.15, 0.15)]
        counts = [math.floor(value) for value in exact]
        for index in sorted(range(3), key=lambda i: (-(exact[i] - counts[i]), i))[:total - sum(counts)]:
            counts[index] += 1
        offset = 0
        for split, count in zip(("train", "val", "test"), counts):
            for group in identifiers[offset:offset + count]:
                assignments[group] = split
            offset += count
    return assignments


def link_or_copy(source: Path, target: Path) -> str:
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        # Cross-device filesystems and Windows configurations may disallow links.
        shutil.copy2(source, target)
        if sha256_file(source) != sha256_file(target):
            raise PreparationError(f"Copy integrity failure: {source.name}")
        return "copy"


def prepare(archive: Path, dataset_root: Path, *, seed: int = 42, strict_inventory: bool = True,
            near_radius: int = 4, near_rmse: float = 6.0) -> dict:
    """Prepare once. Existing prepared output is never overwritten."""
    archive, dataset_root = archive.resolve(), dataset_root.resolve()
    if not archive.is_file() or not archive.is_relative_to(dataset_root):
        raise PreparationError("Archive must be an existing local file inside Dataset")
    if not 0 <= near_radius <= 8 or not math.isfinite(near_rmse) or not 0 <= near_rmse <= 20:
        raise PreparationError("Near-duplicate limits must be radius 0..8 and finite RMSE 0..20")
    output = checked_child(dataset_root, dataset_root / "prepared")
    if output.exists():
        raise PreparationError("Dataset/prepared already exists; preserve it or choose a fresh Dataset root")
    raw = checked_child(dataset_root, dataset_root / "raw")
    raw.mkdir(exist_ok=True)
    archive_hash = sha256_file(archive)
    print(f"Archive SHA-256: {archive_hash}", flush=True)
    if strict_inventory and (archive.stat().st_size != PINNED_ARCHIVE_BYTES or archive_hash != PINNED_ARCHIVE_SHA256):
        raise PreparationError("Archive differs from the verified pinned v1 full download SHA-256/size")
    names = safe_extract(archive, raw / "rdd2022es-v1", archive_hash)
    source = raw / "rdd2022es-v1" / "combined_annotatedv2"
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    expected_names = [row["source_name"] for row in schema["classes"]]
    if (source / "classes.txt").read_text(encoding="utf-8").splitlines() != expected_names:
        raise PreparationError("Archive classes.txt differs from the shared eight-class schema")
    images = sorted(source.glob("*.jpg"))
    labels = {path.stem: path for path in source.glob("*.txt") if path.name != "classes.txt"}
    if strict_inventory and (len(names), len(images), len(labels)) != (51200, 25600, 25599):
        raise PreparationError("Pinned v1 inventory differs: expected 51200 files, 25600 images and 25599 labels")
    output.mkdir()
    errors, samples, fingerprints, exclusions = [], [], {}, []
    audit = {"dataset_ref": DATASET_REF, "dataset_version": DATASET_VERSION,
             "archive": str(archive.relative_to(dataset_root)), "archive_sha256": archive_hash,
             "archive_bytes": archive.stat().st_size, "label_schema_version": schema["schema_version"],
             "archive_files": len(names), "images": len(images), "annotations": len(labels),
             "full_decode_attempts": 0, "bbox_tolerance": 1e-6, "errors": errors, "exclusions": exclusions,
             "known_exif_quarantine": KNOWN_EXIF_QUARANTINE,
             "empty_annotation_interpretation": "No annotated boxes; not proof of a safe or undamaged road.",
             "limitations": ["Perceptual grouping is conservative and may overgroup or miss visually related frames.",
                             "Filename groups and thumbnail hashes cannot establish scene independence or remove all adjacent-scene leakage.",
                             "Country-aware random split is provisional; no geographic or camera-sequence metadata is available."]}
    for index, image in enumerate(images):
        match = NAME.fullmatch(image.stem)
        key = image.stem
        label = labels.get(key)
        sample = {"sample_id": key, "original_group": key.removeprefix("xmirror_"),
                  "country": match[2], "is_mirror": bool(match[1]),
                  "source_image": image.relative_to(dataset_root).as_posix(),
                  "source_label": label.relative_to(dataset_root).as_posix() if label else None,
                  "image_sha256": sha256_file(image), "label_sha256": sha256_file(label) if label else None,
                  "boxes": [], "split": None, "exclusion_reason": None}
        audit["full_decode_attempts"] += 1
        try:
            quarantine = KNOWN_EXIF_QUARANTINE.get(sample["original_group"])
            member_kind = "mirror" if sample["is_mirror"] else "original"
            expected_orientation = quarantine[f"{member_kind}_orientation"] if quarantine else 1
            # Always decode fully before checking the exact observed exception.
            fingerprints[key] = image_fingerprints(image, expected_orientation=expected_orientation)
            sample["width"], sample["height"] = fingerprints[key][3]
            sample["exif_orientation"] = fingerprints[key][6]
            sample["pixel_sha256"] = fingerprints[key][2]
            sample["dhash"] = f"{fingerprints[key][0]:016x}"
            sample["mirror_dhash"] = f"{fingerprints[key][1]:016x}"
            if quarantine:
                if sample["image_sha256"] != quarantine[f"{member_kind}_sha256"]:
                    raise PreparationError(f"{key}: known EXIF quarantine member SHA-256 differs from the recorded v1 observation")
                sample["exclusion_reason"] = "exif_orientation_unverified_labels"
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
            errors.append(f"{key}: image decode failed: {error}")
        if label is None:
            sample["exclusion_reason"] = "documented_missing_label" if key in KNOWN_MISSING_LABELS else "unexpected_missing_label"
            if key not in KNOWN_MISSING_LABELS:
                errors.append(f"{key}: unexpected missing label")
        else:
            try:
                sample["boxes"] = parse_labels(label)
            except (UnicodeError, PreparationError) as error:
                errors.append(str(error))
        samples.append(sample)
        if (index + 1) % 1000 == 0:
            print(f"Decoded/validated {index + 1}/{len(images)} images", flush=True)
    image_ids = {sample["sample_id"] for sample in samples}
    for key in sorted(labels.keys() - image_ids):
        reason = "documented_orphan_label" if key in KNOWN_ORPHAN_LABELS else "unexpected_orphan_label"
        exclusions.append({"sample_id": key, "source_label": labels[key].relative_to(dataset_root).as_posix(),
                           "label_sha256": sha256_file(labels[key]), "exclusion_reason": reason})
        if key not in KNOWN_ORPHAN_LABELS:
            errors.append(f"{key}: unexpected orphan label")
        try:
            orphan_rows = parse_labels(labels[key])
            if key in KNOWN_ORPHAN_LABELS and orphan_rows:
                errors.append(f"{key}: documented orphan was expected to have empty annotations")
        except (UnicodeError, PreparationError) as error:
            errors.append(str(error))
    by_key = {sample["sample_id"]: sample for sample in samples}
    for sample in samples:
        if sample["is_mirror"]:
            original = by_key.get(sample["original_group"])
            if original is None:
                errors.append(f"{sample['sample_id']}: mirror without original")
                continue
            if original["exclusion_reason"] or sample["exclusion_reason"]:
                reason = original["exclusion_reason"] or sample["exclusion_reason"]
                if "missing_label" in reason:
                    reason = "quarantined_missing_label_group"
                original["exclusion_reason"] = sample["exclusion_reason"] = reason
                continue
            mirrored = sorted([[row[0], 1 - row[1], *row[2:]] for row in original["boxes"]])
            actual = sorted(sample["boxes"])
            if len(mirrored) != len(actual) or any(a[0] != b[0] or any(abs(x - y) > 1e-6 for x, y in zip(a[1:], b[1:]))
                                                       for a, b in zip(mirrored, actual)):
                errors.append(f"{sample['sample_id']}: mirror label relationship differs")
            if sample["sample_id"] in fingerprints and original["sample_id"] in fingerprints:
                a, b = fingerprints[sample["sample_id"]][4], fingerprints[original["sample_id"]][5]
                rmse = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))
                if fingerprints[sample["sample_id"]][3] != fingerprints[original["sample_id"]][3] or rmse > 6:
                    errors.append(f"{sample['sample_id']}: mirror image relationship differs (thumbnail RMSE {rmse:.3f})")
        elif f"xmirror_{sample['sample_id']}" not in by_key:
            errors.append(f"{sample['sample_id']}: original without source mirror")
    def save_records():
        audit["quarantined_groups"] = sorted({sample["original_group"] for sample in samples
                                               if sample["exclusion_reason"] in ("quarantined_missing_label_group", "exif_orientation_unverified_labels")})
        audit["image_exclusion_counts"] = dict(Counter(sample["exclusion_reason"] for sample in samples if sample["exclusion_reason"]))
        with (output / "manifest.jsonl").open("w", encoding="utf-8") as stream:
            for sample in samples:
                stream.write(json.dumps(sample, ensure_ascii=False) + "\n")
        write_json(output / "audit.json", audit)
    if errors:
        audit["status"] = "failed_validation"
        save_records()
        raise PreparationError(f"Full validation failed with {len(errors)} error(s); see {output / 'audit.json'}")
    usable = [sample for sample in samples if not sample["exclusion_reason"]]
    if not usable:
        raise PreparationError("No usable samples")
    print("Grouping exact and conservative perceptual duplicates before splitting", flush=True)
    groups, duplicate_stats = group_duplicates(usable, fingerprints, near_radius, near_rmse)
    assignments = assign_splits(usable, groups, seed)
    summary = {"seed": seed, "ratios": {"train": 0.7, "val": 0.15, "test": 0.15},
               "status": "provisional_country_aware_group_split", "fliplr": 0.0,
               "evaluation_originals_only": True, "splits": {}, "group_count": len(assignments)}
    materialized = Counter()
    for split in ("train", "val", "test"):
        (output / "images" / split).mkdir(parents=True)
        (output / "labels" / split).mkdir(parents=True)
        summary["splits"][split] = {"images": 0, "groups": 0, "originals": 0, "mirrors": 0,
                                    "empty_annotations": 0, "countries": {},
                                    "class_boxes": [0] * 8, "class_images": [0] * 8}
    included_groups = defaultdict(set)
    image_hash_splits = defaultdict(set)
    for sample in usable:
        key = sample["sample_id"]
        group = groups.find(key)
        split = assignments[group]
        sample["group_id"] = group
        sample["assigned_split"] = split
        if split != "train" and sample["is_mirror"]:
            sample["exclusion_reason"] = "evaluation_source_mirror_excluded"
            continue
        sample["split"] = split
        entry = summary["splits"][split]
        entry["images"] += 1
        entry["mirrors" if sample["is_mirror"] else "originals"] += 1
        entry["empty_annotations"] += not sample["boxes"]
        entry["countries"][sample["country"]] = entry["countries"].get(sample["country"], 0) + 1
        for row in sample["boxes"]:
            entry["class_boxes"][row[0]] += 1
        for class_id in {row[0] for row in sample["boxes"]}:
            entry["class_images"][class_id] += 1
        included_groups[split].add(group)
        image_hash_splits[sample["image_sha256"]].add(split)
        image_source = dataset_root / sample["source_image"]
        label_source = dataset_root / sample["source_label"]
        materialized[link_or_copy(image_source, output / "images" / split / image_source.name)] += 1
        materialized[link_or_copy(label_source, output / "labels" / split / label_source.name)] += 1
    for split, identifiers in included_groups.items():
        summary["splits"][split]["groups"] = len(identifiers)
    if any(len(values) != 1 for values in image_hash_splits.values()) or any(
            included_groups[a] & included_groups[b] for a, b in (("train", "val"), ("train", "test"), ("val", "test"))):
        raise PreparationError("Internal grouped leakage assertion failed")
    audit.update({"status": "passed_full_content_validation", "duplicate_grouping": duplicate_stats,
                  "materialization": dict(materialized), "grouped_leakage_assertions": "passed",
                  "usable_images_before_evaluation_mirror_exclusion": len(usable),
                  "full_class_boxes": [sum(row[0] == i for sample in usable for row in sample["boxes"]) for i in range(8)],
                  "full_class_images": [sum(any(row[0] == i for row in sample["boxes"]) for sample in usable) for i in range(8)]})
    write_json(output / "split_summary.json", summary)
    save_records()
    # JSON scalars/list are valid YAML; no dependency on a YAML writer is needed.
    yaml = f"path: {json.dumps(output.as_posix())}\ntrain: images/train\nval: images/val\ntest: images/test\nnc: 8\nnames: {json.dumps(expected_names)}\n"
    (output / "data.yaml").write_text(yaml, encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("prepare")
    repository = Path(__file__).resolve().parents[2]
    command.add_argument("--archive", type=Path, default=repository / "Dataset/downloads/rdd2022es-v1.zip")
    command.add_argument("--dataset-root", type=Path, default=repository / "Dataset")
    command.add_argument("--seed", type=int, default=42)
    command.add_argument("--near-radius", type=int, default=4)
    command.add_argument("--near-rmse", type=float, default=6.0)
    args = parser.parse_args(argv)
    try:
        if not args.dataset_root.resolve().is_relative_to((repository / "Dataset").resolve()):
            raise PreparationError("CLI dataset-root must stay inside the repository Dataset directory")
        summary = prepare(args.archive, args.dataset_root, seed=args.seed, near_radius=args.near_radius, near_rmse=args.near_rmse)
    except (PreparationError, OSError, zipfile.BadZipFile) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
