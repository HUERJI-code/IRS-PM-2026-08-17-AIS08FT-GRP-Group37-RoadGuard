"""Exercise range integrity and restart behavior without external downloads."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "roadguard_download_data", Path(__file__).resolve().parents[1] / "model/download_data.py",
)
download_data = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(download_data)


@pytest.fixture
def source(tmp_path, monkeypatch):
    data = b"PK-example-fixed-dataset-archive"
    monkeypatch.setattr(download_data, "ROOT", tmp_path)
    monkeypatch.setattr(download_data, "EXPECTED_SIZE", len(data))
    monkeypatch.setattr(download_data, "CHUNK_SIZE", 7)
    monkeypatch.setattr(download_data.time, "sleep", lambda _: None)
    calls = []

    def fetch(request, timeout):
        start, end = map(int, request.get_header("Range").split("=")[1].split("-"))
        calls.append((start, end))
        response = io.BytesIO(data[start:end + 1])
        response.status = 206
        response.headers = {"Content-Range": f"bytes {start}-{end}/{len(data)}"}
        return response

    monkeypatch.setattr(download_data, "urlopen", fetch)
    return tmp_path, data, calls


def test_download_verifies_ranges_and_reuses_completed_archive(source):
    root, data, calls = source
    path = download_data.download()
    assert path.read_bytes() == data
    record = json.loads(path.with_name("download.json").read_text())
    assert record["sha256"] == hashlib.sha256(data).hexdigest()
    assert record["version"] == 1
    assert len(calls) == 5
    download_data.download()
    assert len(calls) == 5


def test_download_restarts_using_verified_completed_parts(source):
    root, data, calls = source
    directory = root / "Dataset/downloads/rdd2022es-v1.parts"
    directory.mkdir(parents=True)
    (directory / "0000.part").write_bytes(data[:7])
    (directory / "0000.sha256").write_text(hashlib.sha256(data[:7]).hexdigest())
    # Corrupt cached chunks must be fetched again even if their size is right.
    (directory / "0001.part").write_bytes(b"wrong!!")
    (directory / "0001.sha256").write_text(hashlib.sha256(data[7:14]).hexdigest())
    assert download_data.download().read_bytes() == data
    assert (0, 6) not in calls
    assert (7, 13) in calls


def test_download_rejects_server_ignoring_range(source, monkeypatch):
    def fetch(request, timeout):
        response = io.BytesIO(b"an HTML landing page is not the requested data")
        response.status = 200
        response.headers = {}
        return response

    monkeypatch.setattr(download_data, "urlopen", fetch)
    with pytest.raises(RuntimeError, match="byte range"):
        download_data.download()
    assert not (source[0] / "Dataset/downloads/rdd2022es-v1.zip").exists()


def test_download_does_not_overwrite_unrecorded_existing_file(source):
    target = source[0] / "Dataset/downloads/rdd2022es-v1.zip"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"user's existing file")
    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        download_data.download()
    assert target.read_bytes() == b"user's existing file"


def test_download_detects_changed_completed_archive(source):
    path = download_data.download()
    path.write_bytes(b"!" * len(source[1]))
    with pytest.raises(RuntimeError, match="differs"):
        download_data.download()
