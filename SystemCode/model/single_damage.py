"""Validation-only single-subject comparison using hash-verified existing exports."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from roadguard.schemas import Detection
from roadguard.schemas.common import LABELS_BY_ID
from roadguard.vision.primary import PrimaryPolicy, STRATEGIES, overlap, ranking_score, suggest_primary

try:
    from . import inference_experiments as experiments
    from .checkpointing import sha256_file, write_json
    from .train import REPO_ROOT
except ImportError:
    import inference_experiments as experiments
    from checkpointing import sha256_file, write_json
    from train import REPO_ROOT


THRESHOLDS = (0.1, 0.2, 0.3, 0.4, 0.5)
EXPORTS = {
    "standard832": "Dataset/balanced-metrics/balanced70-new-best832/export.json",
    "flip832": "Dataset/inference-followup/flip832/export.json",
}
SELECTION = "calibration max min(typed precision, typed recall), then eight-class macro F1, then recall; stable candidate order on ties"


def partition(group_id):
    value = hashlib.sha256(("single-damage-v1:" + group_id).encode()).hexdigest()
    return "calibration" if int(value[:8], 16) % 10 < 7 else "confirmation"


def convert(row):
    return [Detection(detection_id=str(i), label=LABELS_BY_ID[p["class_id"]],
                      image_width=row["width"], image_height=row["height"],
                      model_version="offline-export", is_demo=False, **p)
            for i, p in enumerate(row["predictions"])]


def select(detections, policy, gate):
    suggestion = suggest_primary(detections, policy)
    if gate:
        return (next((d for d in detections if d.detection_id == suggestion["detection_id"]), None), suggestion)
    eligible = [d for d in detections if d.confidence >= policy.threshold]
    return (max(eligible, key=lambda d: ranking_score(d, policy.strategy), default=None), suggestion)


def metrics(rows, policy, gate=True):
    """Image type metrics; wrong type counts once as FP and once as FN.

    Rows must have <=1 GT. Box overlap is a separate stricter diagnostic.
    Blank-label images participate in precision, specificity and presence scores.
    """
    confusion = [[0] * 9 for _ in range(9)]  # 8 = no annotation / no suggestion
    typed_iou = {"0.3": 0, "0.5": 0}
    ambiguous = 0
    for row in rows:
        if len(row["truth"]) > 1:
            raise ValueError("Multi-object rows cannot be silently reduced to single-object truth")
        prediction, suggestion = select(row["detections"], policy, gate)
        ambiguous += suggestion["status"] == "ambiguous"
        actual = row["truth"][0]["class_id"] if row["truth"] else 8
        predicted = prediction.class_id if prediction is not None else 8
        confusion[actual][predicted] += 1
        if actual == predicted and actual != 8:
            iou = overlap(prediction.bbox_xyxy, row["truth"][0]["bbox_xyxy"])
            for threshold in typed_iou:
                typed_iou[threshold] += iou >= float(threshold)
    positive = sum(sum(r) for r in confusion[:8])
    returned = sum(sum(r[:8]) for r in confusion)
    correct = sum(confusion[i][i] for i in range(8))
    safe_div = lambda a, b: a / b if b else 0.0
    per_class = []
    for i in range(8):
        support, outputs, tp = sum(confusion[i]), sum(r[i] for r in confusion), confusion[i][i]
        per_class.append({"class_id": i, "support": support, "tp": tp,
                          "precision": safe_div(tp, outputs), "recall": safe_div(tp, support),
                          "f1": safe_div(2 * tp, outputs + support)})
    presence_tp = sum(sum(r[:8]) for r in confusion[:8])
    return {"images": len(rows), "positive_images": positive, "negative_images": len(rows) - positive,
            "predicted_images": returned, "tp": correct, "fp": returned - correct, "fn": positive - correct,
            "precision": safe_div(correct, returned), "recall": safe_div(correct, positive),
            "macro_f1": sum(c["f1"] for c in per_class) / 8,
            "presence_precision": safe_div(presence_tp, returned), "presence_recall": safe_div(presence_tp, positive),
            "negative_false_positive_rate": safe_div(sum(confusion[8][:8]), sum(confusion[8])),
            "typed_localization": {key: {"tp": tp, "precision": safe_div(tp, returned), "recall": safe_div(tp, positive)}
                                   for key, tp in typed_iou.items()},
            "ambiguous_images": ambiguous, "per_class": per_class, "confusion_matrix": confusion}


def selection_key(item):
    m = item["calibration"]
    return min(m["precision"], m["recall"]), m["macro_f1"], m["recall"]


def compare(output: Path, root=REPO_ROOT):
    output = output.resolve()
    dataset = (root / "Dataset").resolve()
    if not output.is_relative_to(dataset) or output.exists():
        raise ValueError("Use a fresh output directory inside ignored Dataset")
    output.mkdir(parents=True)
    inputs = {name: {"path": path, "sha256": sha256_file(root / path)} for name, path in EXPORTS.items()}
    # This file is written before predictions are loaded or candidate metrics calculated.
    plan = {"schema_version": "roadguard-single-damage-plan-v1", "inputs": inputs,
            "strategies": list(STRATEGIES), "thresholds": list(THRESHOLDS), "ambiguity_gates": [True, False],
            "selection": SELECTION, "partition": "sha256('single-damage-v1:' + group_id) first8hex mod10 <7 calibration else confirmation",
            "primary_population": "all val originals with zero or one GT; all multi-GT reported separately",
            "manifest_sha256": sha256_file(dataset / "prepared/manifest.jsonl"),
            "weights_sha256": "464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488",
            "source_sha256": {"single_damage.py": sha256_file(Path(__file__)),
                              "primary.py": sha256_file(root / "SystemCode/backend/roadguard/vision/primary.py")},
            "validation_role": "already_used_for_training_and_selection; confirmation is not an independent test",
            "training": False, "external_images": "known six photographs and AI image excluded from selection"}
    write_json(output / "plan.json", plan)
    groups = {}
    for line in (dataset / "prepared/manifest.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["split"] == "val":
            groups[row["sample_id"]] = row["group_id"]
    exports, candidates, baselines = {}, [], []
    for name, info in inputs.items():
        _, rows = experiments.load_export(root / info["path"], root=root)
        for row in rows:
            row["detections"] = convert(row)
            row["partition"] = partition(groups[row["sample_id"]])
        exports[name] = rows
        single = [r for r in rows if len(r["truth"]) <= 1]
        partitions = {part: [r for r in single if r["partition"] == part] for part in ("calibration", "confirmation")}
        for strategy in STRATEGIES:
            for threshold in THRESHOLDS:
                for gate in (True, False):
                    policy = PrimaryPolicy(strategy, threshold)
                    candidates.append({"recipe": name, "strategy": strategy, "threshold": threshold, "gate": gate,
                                       "calibration": metrics(partitions["calibration"], policy, gate)})
        baseline = PrimaryPolicy("confidence", 0.25 if name == "standard832" else 0.3)
        baselines.append({"recipe": name, "strategy": "confidence", "threshold": baseline.threshold, "gate": False,
                          **{part: metrics(part_rows, baseline, False) for part, part_rows in partitions.items()}})
    selected = max(candidates, key=selection_key)
    # Freeze selected settings before accessing confirmation metrics for candidates.
    settings = {key: selected[key] for key in ("recipe", "strategy", "threshold", "gate")}
    write_json(output / "selection.json", settings)
    selected_rows = exports[settings["recipe"]]
    policy = PrimaryPolicy(settings["strategy"], settings["threshold"])
    selected["confirmation"] = metrics([r for r in selected_rows if len(r["truth"]) <= 1 and r["partition"] == "confirmation"], policy, settings["gate"])
    selected["all_single"] = metrics([r for r in selected_rows if len(r["truth"]) <= 1], policy, settings["gate"])
    multi = [r for r in selected_rows if len(r["truth"]) > 1]
    decisions = [select(r["detections"], policy, settings["gate"]) for r in multi]
    challenge = {"images": len(multi), "ground_truth_boxes": sum(len(r["truth"]) for r in multi),
                 "ambiguous_images": sum(s["status"] == "ambiguous" for _, s in decisions),
                 "images_with_suggestion": sum(p is not None for p, _ in decisions),
                 "limitation": "At most one output cannot recover all damage; ambiguity gate does not reliably detect all multi-object photos."}
    report = {"schema_version": "roadguard-single-damage-comparison-v1", "plan_sha256": sha256_file(output / "plan.json"),
              "selection_sha256": sha256_file(output / "selection.json"), "selected": selected, "baselines": baselines,
              "candidates": candidates, "multi_object_challenge": challenge,
              "population": {"total_val": len(selected_rows), "single_gt": sum(len(r["truth"]) == 1 for r in selected_rows),
                             "zero_gt": sum(not r["truth"] for r in selected_rows), "multi_gt": len(multi)},
              "validation_role": plan["validation_role"]}
    write_json(output / "comparison.json", report)
    decisions = [{"sample_id": r["sample_id"], "partition": r["partition"], "truth": r["truth"],
                  "suggestion": select(r["detections"], policy, settings["gate"])[0].model_dump()
                  if select(r["detections"], policy, settings["gate"])[0] is not None else None,
                  "review": suggest_primary(r["detections"], policy)} for r in selected_rows]
    write_json(output / "decisions.json", decisions)
    write_json(output / "status.json", {"status": "complete", "comparison_sha256": sha256_file(output / "comparison.json"),
                                        "decisions_sha256": sha256_file(output / "decisions.json")})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.output)
    print(json.dumps({key: report[key] for key in ("population", "selected", "baselines", "multi_object_challenge")}, indent=2))
