"""Small, dependency-free durability and recovery identity helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    """Flush a same-directory temporary file before replacing the published file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        # POSIX supports directory fsync. Windows os.replace is the atomic publication boundary.
        if os.name != "nt":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))


class RecoveryStore:
    """Two rolling full checkpoints, independent of Ultralytics' stripped last/best."""

    def __init__(self, weights_dir: Path):
        self.latest = weights_dir / "resume-latest.pt"
        self.previous = weights_dir / "resume-previous.pt"

    def publish(self, serialized: bytes) -> None:
        if self.latest.exists():
            atomic_write(self.previous, self.latest.read_bytes())
        atomic_write(self.latest, serialized)


def validate_resume(checkpoint: dict, identity: dict) -> int:
    """Reject mismatched or stripped checkpoints before constructing a model."""
    metadata = checkpoint.get("roadguard")
    if not isinstance(metadata, dict) or metadata.get("identity") != identity:
        raise ValueError("Resume identity mismatch: dataset/config/runtime differ or checkpoint lacks RoadGuard metadata")
    epoch = checkpoint.get("epoch")
    if not isinstance(epoch, int) or epoch < 0 or checkpoint.get("optimizer") is None:
        raise ValueError("Checkpoint is stripped or incomplete; use resume-latest.pt or resume-previous.pt")
    for key in ("scheduler", "rng", "live_model_state", "stopper"):
        if key not in metadata:
            raise ValueError(f"Incomplete recovery state: {key}")
    return epoch + 1
