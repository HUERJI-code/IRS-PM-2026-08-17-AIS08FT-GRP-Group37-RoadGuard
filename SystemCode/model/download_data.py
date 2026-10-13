"""Resumable, version-pinned RDD2022ES download; bulk files stay in Dataset."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.kaggle.com/api/v1/datasets/download/juusos/rdd2022es?datasetVersionNumber=1"
EXPECTED_SIZE = 2_611_933_018
CHUNK_SIZE = 32 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download() -> Path:
    directory = ROOT / "Dataset" / "downloads"
    directory.mkdir(parents=True, exist_ok=True)
    parts = directory / "rdd2022es-v1.parts"
    parts.mkdir(exist_ok=True)
    target = directory / "rdd2022es-v1.zip"
    record = directory / "download.json"
    if target.exists():
        if not record.exists():
            raise RuntimeError("Existing ZIP lacks its download record; refusing to overwrite.")
        previous = json.loads(record.read_text(encoding="utf-8"))
        if target.stat().st_size != EXPECTED_SIZE or sha256(target) != previous["sha256"]:
            raise RuntimeError("Existing ZIP differs from its recorded download.")
        print("Verified existing version 1 ZIP.", flush=True)
        return target

    def fetch(index: int) -> Path:
        start = index * CHUNK_SIZE
        end = min(start + CHUNK_SIZE, EXPECTED_SIZE) - 1
        size = end - start + 1
        part = parts / f"{index:04d}.part"
        checksum = part.with_suffix(".sha256")
        if part.exists() and checksum.exists() and part.stat().st_size == size:
            if sha256(part) == checksum.read_text(encoding="ascii").strip():
                return part
        for attempt in range(3):
            try:
                request = Request(URL, headers={
                    "Range": f"bytes={start}-{end}",
                    "User-Agent": "RoadGuard-data-preparation/1.0",
                    "Accept-Encoding": "identity",
                })
                temporary = part.with_suffix(".incomplete")
                with urlopen(request, timeout=60) as response, temporary.open("wb") as output:
                    expected_range = f"bytes {start}-{end}/{EXPECTED_SIZE}"
                    if response.status != 206 or response.headers.get("Content-Range") != expected_range:
                        raise RuntimeError("Download source did not honor the pinned byte range.")
                    count = 0
                    digest = hashlib.sha256()
                    while block := response.read(min(1024 * 1024, size - count + 1)):
                        count += len(block)
                        if count > size:
                            raise RuntimeError("Download exceeded requested byte range.")
                        output.write(block)
                        digest.update(block)
                    if count != size:
                        raise RuntimeError("Incomplete download range.")
                    output.flush()
                    os.fsync(output.fileno())
                temporary.replace(part)
                checksum.write_text(digest.hexdigest() + "\n", encoding="ascii")
                return part
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
        raise AssertionError("unreachable")

    count = (EXPECTED_SIZE + CHUNK_SIZE - 1) // CHUNK_SIZE
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(fetch, index) for index in range(count)]
        for done, future in enumerate(as_completed(futures), 1):
            future.result()
            print(f"Download parts verified: {done}/{count}", flush=True)
    temporary = target.with_suffix(".assembling")
    digest = hashlib.sha256()
    with temporary.open("wb") as output:
        for index in range(count):
            with (parts / f"{index:04d}.part").open("rb") as part:
                for block in iter(lambda: part.read(1024 * 1024), b""):
                    output.write(block)
                    digest.update(block)
        output.flush()
        os.fsync(output.fileno())
    if temporary.stat().st_size != EXPECTED_SIZE:
        raise RuntimeError("Assembled archive has unexpected size.")
    metadata = {
        "dataset_ref": "juusos/rdd2022es", "version": 1,
        "source_url": URL, "size_bytes": EXPECTED_SIZE,
        "sha256": digest.hexdigest(),
        "content_validation": "pending_full_archive_and_annotation_audit",
    }
    record.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(target)
    print(json.dumps(metadata), flush=True)
    return target


if __name__ == "__main__":
    download()
