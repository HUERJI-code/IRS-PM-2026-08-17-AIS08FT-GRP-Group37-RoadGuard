"""GA evaluation script: ablation, best-known solution and gap bookkeeping on saved matrices."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "routing_ga_evaluation", ROOT / "SystemCode/experiments/routing/evaluate_ga.py")
EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVAL)
FAST = {"population_size": 16, "max_generations": 20, "patience_generations": 8}
LONG = {"population_size": 20, "max_generations": 30, "patience_generations": 10}


def run(tmp_path, **kwargs):
    options = {"task_counts": (15,), "providers": ("google_routes",), "shifts": ("limited",),
               "seeds": [1, 2], "long_seeds": [101, 102], "ga_overrides": FAST, "long_overrides": LONG}
    options.update(kwargs)
    return EVAL.evaluate(tmp_path / "out", **options)


def key(r):
    return (int(r["unassigned_p1"]), int(r["unassigned_p2"]), int(r["unassigned_p3"]), float(r["objective"]))


def test_best_known_is_no_worse_than_any_run_and_seeded_ga_never_loses(tmp_path):
    summary = run(tmp_path)["scenarios"]["google_routes/limited/15"]
    with (tmp_path / "out/raw_runs.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["method"] for r in rows} == {"greedy", "ga_pure", "ga_seeded", "long_run"}
    bks = (*summary["bks_unassigned_p1_p2_p3"], summary["bks_objective"])
    assert all(key(r) >= tuple(bks) for r in rows)
    greedy = next(key(r) for r in rows if r["method"] == "greedy")
    assert all(key(r) <= greedy for r in rows if r["method"] == "ga_seeded")
    assert summary["ga_seeded"]["worse_than_greedy"] == 0
    for method in ("ga_pure", "ga_seeded"):
        m = summary[method]
        assert m["better_than_greedy"] + m["equal_to_greedy"] + m["worse_than_greedy"] == m["runs"] == 2
        # Gaps are only averaged over runs covering as many tasks as the best-known solution.
        covered = m["runs"] - m["fewer_tasks_than_bks"]
        assert m.get("gap_to_bks_percent", {"runs": 0})["runs"] == covered


def test_outputs_record_matrix_hash_routes_and_code_version(tmp_path):
    run(tmp_path)
    out = tmp_path / "out"
    recorded = json.loads((ROOT / "SystemCode/experiments/routing/results/google-shift480-v1/summary.json")
                          .read_text(encoding="utf-8"))["scenarios"]["15"]["matrix_sha256"]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["scenarios"]["google_routes/limited/15"]["matrix_sha256"] == recorded
    best = json.loads((out / "best_known.json").read_text(encoding="utf-8"))["google_routes/limited/15"]
    assigned = [task for route in best["routes_task_ids"] for task in route]
    assert len(assigned) == len(set(assigned)) == 15 - sum(best["unassigned_p1_p2_p3"])
    metadata = json.loads((out / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["ga_parameters"]["seed_with_greedy"] is False and "commit" in metadata["code"]


def test_tampered_matrix_is_rejected(tmp_path, monkeypatch):
    fake_results = tmp_path / "results"
    source = ROOT / "SystemCode/experiments/routing/results/google-shift480-v1"
    target = fake_results / "google-shift480-v1"
    target.mkdir(parents=True)
    (target / "summary.json").write_text((source / "summary.json").read_text(encoding="utf-8"), encoding="utf-8")
    matrix = json.loads((source / "matrix_15.json").read_text(encoding="utf-8"))
    matrix["duration_minutes"][0][1] += 1.0
    (target / "matrix_15.json").write_text(json.dumps(matrix), encoding="utf-8")
    monkeypatch.setattr(EVAL, "RESULTS", fake_results)
    with pytest.raises(ValueError, match="recorded hash"):
        run(tmp_path)
    assert not (tmp_path / "out").exists()


def test_refuses_to_overwrite(tmp_path):
    (tmp_path / "out").mkdir()
    with pytest.raises(FileExistsError):
        run(tmp_path)
