"""Try the experimental single-damage policy without changing the server manifest."""

import argparse
from io import BytesIO
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from roadguard.images import ImageStore
from roadguard.vision.real import LocalVisionDetector
from roadguard.vision.primary import PrimaryPolicy

try:
    from .benchmark_cpu import configure_runtime_environment
    from .checkpointing import sha256_file, write_json
    from .single_damage import select
    from .train import REPO_ROOT
except ImportError:
    from benchmark_cpu import configure_runtime_environment
    from checkpointing import sha256_file, write_json
    from single_damage import select
    from train import REPO_ROOT


def load_selection(experiment: Path):
    status = json.loads((experiment / "status.json").read_text(encoding="utf-8"))
    comparison_path = experiment / "comparison.json"
    if status.get("status") != "complete" or status.get("comparison_sha256") != sha256_file(comparison_path):
        raise ValueError("Single-damage comparison must be complete and hash verified")
    report = json.loads(comparison_path.read_text(encoding="utf-8"))
    plan = json.loads((experiment / "plan.json").read_text(encoding="utf-8"))
    selection = json.loads((experiment / "selection.json").read_text(encoding="utf-8"))
    if (report.get("schema_version") != "roadguard-single-damage-comparison-v1"
            or report.get("plan_sha256") != sha256_file(experiment / "plan.json")
            or report.get("selection_sha256") != sha256_file(experiment / "selection.json")
            or selection != {k: report["selected"][k] for k in ("recipe", "strategy", "threshold", "gate")}
            or set(selection) != {"recipe", "strategy", "threshold", "gate"}
            or selection["recipe"] != "standard832" or type(selection["gate"]) is not bool):
        raise ValueError("Unsupported or changed single-damage recipe; this runner supports standard832 only")
    # The exact selected implementation must match the evaluated source.
    for name, path in {"single_damage.py": Path(__file__).with_name("single_damage.py"),
                       "primary.py": REPO_ROOT / "SystemCode/backend/roadguard/vision/primary.py"}.items():
        if sha256_file(path) != plan["source_sha256"][name]:
            raise ValueError("Selection implementation changed since evaluation")
    policy = PrimaryPolicy(selection["strategy"], selection["threshold"])
    return selection, plan, policy


def run(image_paths, experiment: Path, source_manifest: Path, output: Path):
    output = output.resolve()
    if not output.is_relative_to((REPO_ROOT / "Dataset").resolve()) or output.exists():
        raise ValueError("Use a fresh output directory inside ignored Dataset")
    selection, plan, policy = load_selection(experiment)
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    if manifest["weights_sha256"] != plan["weights_sha256"] or manifest["inference"] != {"conf": 0.25, "iou": 0.7, "imgsz": 832}:
        raise ValueError("Expected the evaluated best YOLO11s checkpoint and standard832 source manifest")
    if len(image_paths) != len(set(p.resolve() for p in image_paths)):
        raise ValueError("Repeated image paths are not allowed")
    output.mkdir(parents=True)
    configure_runtime_environment(output)
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    from PIL import Image, ImageDraw
    manifest["inference"]["conf"] = policy.threshold
    manifest["model_version"] += "-single-damage-experiment"
    write_json(output / "inference_manifest.json", manifest)
    detector = LocalVisionDetector(output / "inference_manifest.json")
    store = ImageStore(output / "prepared")
    records = []
    write_json(output / "run-plan.json", {"comparison_sha256": sha256_file(experiment / "comparison.json"),
                                          "source_manifest_sha256": sha256_file(source_manifest),
                                          "runner_sha256": sha256_file(Path(__file__)),
                                          "selection": selection, "images": [{"path": str(p.resolve()), "sha256": sha256_file(p)} for p in image_paths],
                                          "role": "qualitative known-image checks, not independent accuracy evaluation"})
    for index, path in enumerate(image_paths):
        data = store.prepare(path.read_bytes())
        detections = detector.detect(data)
        candidate, ambiguity = select(detections, policy, selection["gate"])
        # Validate actual backend precision as well as requested settings.
        backend = detector._model.predictor.model
        if backend.fp16 or detector._model.predictor.args.quantize is not None:
            raise ValueError("Actual prediction backend must be FP32")
        with Image.open(BytesIO(data.content)) as source:
            image = source.convert("RGB")
        draw = ImageDraw.Draw(image)
        if candidate is not None:
            draw.rectangle(candidate.bbox_xyxy, outline="red", width=max(3, image.width // 300))
            draw.text((candidate.bbox_xyxy[0], max(0, candidate.bbox_xyxy[1] - 14)),
                      f"{candidate.label} {candidate.confidence:.3f} (REVIEW)", fill="red", stroke_width=1, stroke_fill="white")
        image.thumbnail((1440, 1440))
        preview = output / f"{index + 1:02d}-{path.stem}.jpg"
        image.save(preview, quality=90)
        record = {"image": str(path.resolve()), "image_sha256": sha256_file(path),
                  "width": data.width, "height": data.height,
                  "main_detection": candidate.model_dump(mode="json") if candidate is not None else None,
                  "review_required": candidate is not None,
                  "ambiguity": ambiguity, "raw_detections": [d.model_dump(mode="json") for d in detections],
                  "annotated_image": preview.name, "selection": selection,
                  "note": "At most one suggested main box, not an accepted task. No suggestion does not prove no damage. All raw evidence retained."}
        write_json(output / f"{index + 1:02d}-result.json", record)
        records.append(record)
        print(json.dumps({"image": path.name, "main": record["main_detection"], "ambiguity": ambiguity["status"]}), flush=True)
    write_json(output / "results.json", {"status": "complete", "run_plan_sha256": sha256_file(output / "run-plan.json"),
                                        "weights_sha256": detector.weights_sha256, "records": records})
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, action="append", required=True)
    parser.add_argument("--experiment", type=Path, default=REPO_ROOT / "Dataset/single-damage-v1")
    parser.add_argument("--manifest", type=Path, default=REPO_ROOT / "Dataset/balanced70/selected_model_manifest.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.image, args.experiment, args.manifest, args.output)
