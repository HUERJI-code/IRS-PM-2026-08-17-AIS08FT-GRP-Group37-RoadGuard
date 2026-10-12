"""The shipped consumer example exercises real handlers without external services."""

import importlib.util
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient

from roadguard.config import load_settings
from roadguard.main import create_app


SCRIPT = Path(__file__).resolve().parents[1] / "examples" / "handoff_demo.py"


def test_handoff_example_validates_full_workflow_and_retains_history(tmp_path):
    spec = importlib.util.spec_from_file_location("handoff_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    settings = load_settings({"ROADGUARD_DB_PATH": str(tmp_path / "handoff.sqlite3")})
    with TestClient(create_app(settings)) as client:
        result = module.run_demo(client)
        assert result["source"] == "actual_http_responses" and result["is_demo"]
        assert result["baseline_revision"] == 0 and result["final_revision"] == 4
        assert client.get("/api/v1/inspections").json()["total"] == 4
        assert client.get("/api/v1/tasks?status=completed").json()["total"] == 1
        assert client.get("/api/v1/tasks?status=cancelled").json()["total"] == 1
        # A second explicit run uses fresh request keys, not silent fixed-ID replay.
        again = module.run_demo(client)
        assert again["baseline_revision"] == 4 and again["final_revision"] == 8


def test_example_cli_requires_explicit_writes_and_works_from_other_cwd(tmp_path):
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 2 and "--confirm-demo-writes" in result.stderr
