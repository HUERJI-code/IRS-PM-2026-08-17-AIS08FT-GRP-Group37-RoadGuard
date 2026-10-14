"""Verify and install an explicitly downloaded, trusted RoadGuard release asset."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "SystemCode/model/releases/roadguard-single-v1.json"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def install(source: Path, *, root: Path = ROOT, manifest_path: Path = MANIFEST) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = source.resolve(strict=True)
    destination = (root / manifest["weights_path"]).resolve()
    allowed = root.resolve() / "SystemCode/backend/roadguard/model"
    if not destination.is_relative_to(allowed) or destination.suffix != ".pt":
        raise ValueError("Model destination must be a .pt file inside SystemCode/backend/roadguard/model")
    if source.stat().st_size != manifest["weights_bytes"] or digest(source) != manifest["weights_sha256"]:
        raise ValueError("Downloaded model size or SHA-256 does not match the release manifest")
    if destination.exists():
        if digest(destination) != manifest["weights_sha256"]:
            raise ValueError("A different model already occupies the release path; no file was overwritten")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".model-", suffix=".partial", dir=destination.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as input_file:
            shutil.copyfileobj(input_file, output)
            output.flush()
            os.fsync(output.fileno())
        if digest(temporary) != manifest["weights_sha256"]:
            raise ValueError("Copied model checksum mismatch")
        # Hard-link publication is atomic and refuses to overwrite a concurrent install.
        os.link(temporary, destination)
    except FileExistsError:
        if digest(destination) != manifest["weights_sha256"]:
            raise ValueError("A different model was installed concurrently") from None
    finally:
        temporary.unlink(missing_ok=True)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="Trusted release .pt downloaded from the private repository")
    args = parser.parse_args()
    print(f"Verified model installed: {install(args.file)}")
