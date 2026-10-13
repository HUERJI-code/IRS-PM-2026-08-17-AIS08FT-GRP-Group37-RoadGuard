"""Create a tiny recovery-only run from the already frozen train/val split."""

import json
import os
from pathlib import Path
import random
import shutil


ROOT = Path(__file__).resolve().parents[2]


def prepare_smoke() -> Path:
    dataset = ROOT / "Dataset"
    path = dataset / "smoke-config.json"
    if path.exists():
        raise ValueError("Existing smoke configuration will not be overwritten")
    prepared = dataset / "prepared"
    audit = json.loads((prepared / "audit.json").read_text(encoding="utf-8"))
    if audit["status"] != "passed_full_content_validation":
        raise ValueError("Smoke requires completed full dataset validation")
    records = [json.loads(line) for line in (prepared / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    target = dataset / "smoke"
    target.mkdir(exist_ok=False)
    selected = []
    for split, count in (("train", 64), ("val", 32)):
        candidates = [row for row in records if row["split"] == split]
        random.Random(42).shuffle(candidates)
        chosen = []
        # Include a source example of each available class for API/shape testing;
        # never use held-out test images or claim these subset metrics as accuracy.
        for class_id in range(8):
            match = next((row for row in candidates if any(box[0] == class_id for box in row["boxes"])), None)
            if match is not None and match not in chosen:
                chosen.append(match)
        chosen.extend(row for row in candidates if row not in chosen)
        chosen = chosen[:count]
        for kind, extension in (("images", ".jpg"), ("labels", ".txt")):
            destination = target / kind / split
            destination.mkdir(parents=True)
            for row in chosen:
                source = prepared / kind / split / (row["sample_id"] + extension)
                output = destination / source.name
                try:
                    os.link(source, output)
                except OSError:
                    shutil.copy2(source, output)
        selected.extend(chosen)
    groups = {split: {row["group_id"] for row in selected if row["split"] == split} for split in ("train", "val")}
    if groups["train"] & groups["val"]:
        raise ValueError("Smoke crossed frozen split groups")
    (target / "manifest.jsonl").write_text("".join(json.dumps(row) + "\n" for row in selected), encoding="utf-8", newline="\n")
    names = [row["source_name"] for row in json.loads((ROOT / "SystemCode/model/label_schema.json").read_text(encoding="utf-8"))["classes"]]
    (target / "data.yaml").write_text(
        f"path: {json.dumps(target.as_posix())}\ntrain: images/train\nval: images/val\nnc: 8\nnames: {json.dumps(names)}\n",
        encoding="utf-8", newline="\n",
    )
    config = json.loads((ROOT / "SystemCode/model/training.example.json").read_text(encoding="utf-8"))
    config.update(data="Dataset/smoke/data.yaml", manifest="Dataset/smoke/manifest.jsonl",
                  run_name="recovery-smoke", model_version="yolo11n-recovery-smoke-not-a-quality-model")
    config["train"].update(epochs=2, imgsz=320, batch=8, workers=0, patience=2)
    config["inference"]["imgsz"] = 320
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Recovery-only subset prepared: {len(selected)} train/val images; no test images.")
    return path


if __name__ == "__main__":
    print(prepare_smoke())
