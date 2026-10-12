"""Actual decode, normalization, upload bounds and generated-file storage."""

from dataclasses import FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import os
from pathlib import Path
import struct
from types import SimpleNamespace
import uuid
import zlib

from PIL import Image, PngImagePlugin
import pytest

from roadguard.errors import AppError
from roadguard.images import ImageStore, MAX_UPLOAD_BYTES, PreparedImage


def encoded(format="PNG", size=(3, 2), **options):
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=format, **options)
    return output.getvalue()


def assert_error(code, status, operation):
    with pytest.raises(AppError) as raised:
        operation()
    assert (raised.value.code, raised.value.status_code) == (code, status)
    return raised.value


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_supported_images_are_decoded_to_metadata_free_rgb_png(tmp_path, format):
    original = encoded(format)
    store = ImageStore(tmp_path / "not-created")
    prepared = store.prepare(original)
    assert not store.root.exists()
    assert (prepared.width, prepared.height) == (3, 2)
    assert prepared.source_sha256 == hashlib.sha256(original).hexdigest()
    with Image.open(BytesIO(prepared.content)) as image:
        image.load()
        assert image.format == "PNG" and image.mode == "RGB"
        assert image.size == (3, 2) and image.info == {}
    with pytest.raises(FrozenInstanceError):
        prepared.width = 4


def test_exif_orientation_changes_dimensions_and_is_removed(tmp_path):
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "private author"
    source = Image.new("RGB", (2, 3))
    source.putdata([(255, 0, 0)] * 2 + [(0, 255, 0)] * 2 + [(0, 0, 255)] * 2)
    output = BytesIO()
    source.save(output, format="JPEG", exif=exif, quality=100, subsampling=0)
    original = output.getvalue()
    prepared = ImageStore(tmp_path).prepare(original)
    assert (prepared.width, prepared.height) == (3, 2)
    with Image.open(BytesIO(prepared.content)) as image:
        assert not image.getexif()
        assert "exif" not in image.info
        red, _, blue = image.getpixel((0, 0))
        assert blue > red


def test_png_metadata_does_not_survive_and_hash_uses_original_bytes(tmp_path):
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "sensitive location")
    first, second = encoded(), encoded(pnginfo=metadata)
    store = ImageStore(tmp_path)
    one, two = store.prepare(first), store.prepare(second)
    assert one.content == two.content
    assert one.source_sha256 != two.source_sha256
    assert b"sensitive location" not in two.content


@pytest.mark.parametrize("data", [b"", b"not an image", b"\xff\xd8truncated", None, "not bytes"])
def test_invalid_data_is_rejected_without_leaking_upload(tmp_path, data):
    error = assert_error("invalid_image", 422, lambda: ImageStore(tmp_path).prepare(data))
    assert "truncated" not in error.message


@pytest.mark.parametrize("format", ["GIF", "BMP", "TIFF"])
def test_recognized_unsupported_formats_are_rejected(tmp_path, format):
    assert_error("unsupported_image_type", 415, lambda: ImageStore(tmp_path).prepare(encoded(format)))


def test_corrupt_supported_image_and_animation_are_rejected(tmp_path):
    store = ImageStore(tmp_path)
    assert_error("invalid_image", 422, lambda: store.prepare(encoded()[:-15]))
    output = BytesIO()
    Image.new("RGB", (3, 2), "red").save(output, format="PNG", save_all=True, append_images=[Image.new("RGB", (3, 2), "blue")])
    assert_error("invalid_image", 422, lambda: store.prepare(output.getvalue()))


def test_upload_byte_limit_and_exact_boundary(tmp_path, monkeypatch):
    store = ImageStore(tmp_path)
    assert_error("image_too_large", 413, lambda: store.prepare(b"x" * (MAX_UPLOAD_BYTES + 1)))
    data = encoded()
    monkeypatch.setattr("roadguard.images.MAX_UPLOAD_BYTES", len(data))
    assert store.prepare(data).width == 3
    monkeypatch.setattr("roadguard.images.MAX_UPLOAD_BYTES", len(data) - 1)
    assert_error("image_too_large", 413, lambda: store.prepare(data))


def test_pixel_limit_is_checked_before_verify_or_full_decode(tmp_path, monkeypatch):
    monkeypatch.setattr("roadguard.images.MAX_IMAGE_PIXELS", 5)
    def forbidden(*args, **kwargs):
        raise AssertionError("full decode should not run")
    monkeypatch.setattr(PngImagePlugin.PngImageFile, "load", forbidden)
    monkeypatch.setattr(PngImagePlugin.PngImageFile, "verify", forbidden)
    assert_error("image_too_large", 413, lambda: ImageStore(tmp_path).prepare(encoded()))


def test_decompression_bomb_header_is_rejected(tmp_path):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 90000, 90000, 8, 2, 0, 0, 0)) + chunk(b"IDAT", b"")
    assert_error("image_too_large", 413, lambda: ImageStore(tmp_path).prepare(data))


def test_storage_creation_exclusive_save_lookup_and_targeted_cleanup(tmp_path):
    root = tmp_path / "images"
    store = ImageStore(root)
    identifier = uuid.uuid4().hex
    assert not root.exists()
    prepared = store.prepare(encoded())
    store.save(identifier, prepared)
    target = store.path(identifier)
    assert target == root / f"{identifier}.png"
    assert target.read_bytes() == prepared.content
    assert list(root.iterdir()) == [target]
    other = root / "unrelated.txt"
    other.write_text("keep")
    different = store.prepare(encoded(size=(4, 4)))
    assert_error("image_already_exists", 409, lambda: store.save(identifier, different))
    assert target.read_bytes() == prepared.content
    assert not list(root.glob("*.tmp"))
    store.delete(identifier)
    store.delete(identifier)
    assert other.read_text() == "keep"
    assert_error("image_not_found", 404, lambda: store.path(identifier))


def test_concurrent_saves_publish_one_complete_image_without_overwrite(tmp_path):
    store = ImageStore(tmp_path / "images")
    identifier = uuid.uuid4().hex
    inputs = [store.prepare(encoded(size=size)) for size in ((3, 2), (4, 4))]
    def save(image):
        try:
            store.save(identifier, image)
            return "saved"
        except AppError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(save, inputs))
    assert sorted(outcomes) == ["image_already_exists", "saved"]
    assert store.path(identifier).read_bytes() in [image.content for image in inputs]
    assert list(store.root.iterdir()) == [store.path(identifier)]


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length path spelling regression.")
def test_windows_extended_prefix_during_creation_is_not_a_false_path_escape(tmp_path, monkeypatch):
    store = ImageStore(tmp_path / "images")
    identifier = uuid.uuid4().hex
    target = store.root / f"{identifier}.png"
    prepared = store.prepare(encoded())
    resolve = Path.resolve
    def extended_resolve(path, *args, **kwargs):
        result = resolve(path, *args, **kwargs)
        if path in (store.root, target):
            return Path("\\\\?\\" + str(result))
        return result
    monkeypatch.setattr(Path, "resolve", extended_resolve)
    store.save(identifier, prepared)
    assert store.path(identifier).read_bytes() == prepared.content
    assert_error("image_already_exists", 409, lambda: store.save(identifier, prepared))
    store.delete(identifier)
    assert not target.exists()


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_windows_rename_collision_errors_preserve_the_complete_winner(tmp_path, monkeypatch, winerror):
    store = ImageStore(tmp_path)
    identifier = uuid.uuid4().hex
    loser, winner = store.prepare(encoded()), store.prepare(encoded(size=(4, 4)))
    target = tmp_path / f"{identifier}.png"
    def raced_rename(source, destination):
        assert Path(source).read_bytes() == loser.content
        Path(destination).write_bytes(winner.content)
        error = PermissionError("private Windows collision details")
        error.winerror = winerror
        raise error
    monkeypatch.setattr("roadguard.images.os", SimpleNamespace(name="nt", fsync=os.fsync, rename=raced_rename))
    assert_error("image_already_exists", 409, lambda: store.save(identifier, loser))
    assert target.read_bytes() == winner.content
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_windows_permission_errors_without_a_destination_remain_storage_failures(tmp_path, monkeypatch, winerror):
    store = ImageStore(tmp_path)
    identifier = uuid.uuid4().hex
    prepared = store.prepare(encoded())
    def denied_rename(*args):
        error = PermissionError("private Windows permission details")
        error.winerror = winerror
        raise error
    monkeypatch.setattr("roadguard.images.os", SimpleNamespace(name="nt", fsync=os.fsync, rename=denied_rename))
    assert_error("image_storage_unavailable", 503, lambda: store.save(identifier, prepared))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("identifier", ["../outside", "/absolute", "a" * 31, "A" * 32, "g" * 32, "", None])
def test_arbitrary_identifiers_cannot_access_or_write_paths(tmp_path, identifier):
    store = ImageStore(tmp_path / "images")
    prepared = store.prepare(encoded())
    assert_error("validation_error", 422, lambda: store.save(identifier, prepared))
    assert_error("validation_error", 422, lambda: store.delete(identifier))
    assert_error("image_not_found", 404, lambda: store.path(identifier))
    assert not store.root.exists()


def test_save_failure_cleans_only_its_generated_temporary_file(tmp_path, monkeypatch):
    store = ImageStore(tmp_path / "images")
    prepared = store.prepare(encoded())
    def fail(*args):
        raise OSError("private-secret failure")
    monkeypatch.setattr(os, "fsync", fail)
    error = assert_error("image_storage_unavailable", 503, lambda: store.save(uuid.uuid4().hex, prepared))
    assert list(store.root.iterdir()) == []
    assert "private-secret" not in error.message


def test_existing_temporary_name_is_never_deleted(tmp_path, monkeypatch):
    store = ImageStore(tmp_path)
    identifier, temporary_id = uuid.uuid4().hex, uuid.uuid4()
    temporary = tmp_path / f".{identifier}-{temporary_id.hex}.tmp"
    temporary.write_bytes(b"existing unrelated data")
    monkeypatch.setattr("roadguard.images.uuid.uuid4", lambda: temporary_id)
    assert_error("image_storage_unavailable", 503, lambda: store.save(identifier, store.prepare(encoded())))
    assert temporary.read_bytes() == b"existing unrelated data"


def test_non_directory_storage_root_is_unavailable(tmp_path):
    root = tmp_path / "file"
    root.write_text("private root")
    store = ImageStore(root)
    assert_error("image_storage_unavailable", 503, lambda: store.save(uuid.uuid4().hex, store.prepare(encoded())))
    assert root.read_text() == "private root"


def test_unsafe_root_resolution_is_rejected_without_creating_files(tmp_path, monkeypatch):
    root, outside = tmp_path / "images", tmp_path / "outside"
    store = ImageStore(root)
    resolve = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, *args, **kwargs: outside if self == root else resolve(self, *args, **kwargs))
    identifier = uuid.uuid4().hex
    assert_error("image_storage_unavailable", 503, lambda: store.save(identifier, store.prepare(encoded())))
    assert not root.exists() and not outside.exists()


def test_target_symlink_check_fails_closed_without_platform_symlink_privilege(tmp_path, monkeypatch):
    store = ImageStore(tmp_path)
    identifier = uuid.uuid4().hex
    target = tmp_path / f"{identifier}.png"
    is_symlink = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: self == target or is_symlink(self))
    assert_error("image_storage_unavailable", 503, lambda: store.path(identifier))
    assert_error("image_storage_unavailable", 503, lambda: store.delete(identifier))
    assert_error("image_storage_unavailable", 503, lambda: store.save(identifier, store.prepare(encoded())))
    assert not target.exists()


def test_generated_filename_symlink_cannot_read_or_delete_outside_root(tmp_path):
    root = tmp_path / "images"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    identifier = uuid.uuid4().hex
    try:
        (root / f"{identifier}.png").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symbolic links requires platform permissions.")
    store = ImageStore(root)
    assert_error("image_storage_unavailable", 503, lambda: store.path(identifier))
    assert_error("image_storage_unavailable", 503, lambda: store.delete(identifier))
    assert_error("image_storage_unavailable", 503, lambda: store.save(identifier, store.prepare(encoded())))
    assert outside.read_text() == "keep"
