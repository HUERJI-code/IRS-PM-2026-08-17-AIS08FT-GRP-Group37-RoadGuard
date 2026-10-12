"""Decode and normalize uploads, then store only generated image filenames."""

from dataclasses import dataclass
import hashlib
from io import BytesIO
import os
from pathlib import Path
import re
import uuid
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from roadguard.errors import AppError


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
_ID = re.compile(r"[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class PreparedImage:
    content: bytes
    width: int
    height: int
    source_sha256: str


def _storage_error():
    return AppError("image_storage_unavailable", "Image storage is unavailable.", 503)


def _canonical(path: Path) -> Path:
    resolved = str(path.resolve())
    # During concurrent creation Windows realpath can retain its extended-length
    # prefix. Normalize that spelling, while keeping the resolved destination.
    if os.name == "nt":
        if resolved.startswith("\\\\?\\UNC\\"):
            resolved = "\\\\" + resolved[8:]
        elif (
            resolved.startswith("\\\\?\\") and len(resolved) >= 7
            and resolved[4] in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
            and resolved[5:7] == ":\\"
        ):
            resolved = resolved[4:]
    return Path(resolved)


class ImageStore:
    def __init__(self, root: Path):
        self.root = Path(os.path.abspath(root))

    def prepare(self, data: bytes) -> PreparedImage:
        if type(data) is not bytes or not data:
            raise AppError("invalid_image", "A valid nonempty image is required.", 422)
        if len(data) > MAX_UPLOAD_BYTES:
            raise AppError("image_too_large", "The uploaded image exceeds the allowed size.", 413)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as source:
                    if source.format not in ("PNG", "JPEG"):
                        raise AppError("unsupported_image_type", "Only PNG and JPEG images are supported.", 415)
                    if source.width * source.height > MAX_IMAGE_PIXELS:
                        raise AppError("image_too_large", "The uploaded image exceeds the allowed size.", 413)
                    if getattr(source, "is_animated", False) or getattr(source, "n_frames", 1) != 1:
                        raise AppError("invalid_image", "Animated images are not supported.", 422)
                    source.verify()
                with Image.open(BytesIO(data)) as source:
                    source.load()
                    oriented = ImageOps.exif_transpose(source).convert("RGB")
                    clean = Image.new("RGB", oriented.size)
                    clean.paste(oriented)
                    output = BytesIO()
                    clean.save(output, format="PNG")
                    return PreparedImage(output.getvalue(), clean.width, clean.height, hashlib.sha256(data).hexdigest())
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise AppError("image_too_large", "The uploaded image exceeds the allowed size.", 413) from None
        except (UnidentifiedImageError, OSError, ValueError, SyntaxError, EOFError, OverflowError):
            raise AppError("invalid_image", "The uploaded image could not be decoded.", 422) from None

    def _target(self, inspection_id: str, lookup: bool = False) -> Path:
        if not isinstance(inspection_id, str) or not _ID.fullmatch(inspection_id):
            if lookup:
                raise AppError("image_not_found", "The inspection image was not found.", 404)
            raise AppError("validation_error", "The inspection image identifier is invalid.", 422)
        try:
            if _canonical(self.root) != self.root or (self.root.exists() and not self.root.is_dir()):
                raise _storage_error()
            target = self.root / f"{inspection_id}.png"
            if target.is_symlink() or _canonical(target).parent != self.root:
                raise _storage_error()
            return target
        except OSError:
            raise _storage_error() from None

    def save(self, inspection_id: str, image: PreparedImage) -> None:
        target = self._target(inspection_id)
        if not isinstance(image, PreparedImage) or type(image.content) is not bytes or not image.content:
            raise AppError("invalid_image", "A prepared image is required.", 422)
        temporary = self.root / f".{inspection_id}-{uuid.uuid4().hex}.tmp"
        created_temporary = False
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self._target(inspection_id)
            with temporary.open("xb") as stream:
                created_temporary = True
                stream.write(image.content)
                stream.flush()
                os.fsync(stream.fileno())
            # Windows rename refuses existing destinations. On POSIX rename can
            # overwrite, so use exclusive hard-link publication instead.
            self._target(inspection_id)
            try:
                if os.name == "nt":
                    os.rename(temporary, target)
                else:
                    os.link(temporary, target)
            except OSError as error:
                # A concurrent Windows winner can make rename report access denied
                # or a sharing/lock violation rather than ERROR_ALREADY_EXISTS.
                # Treat this as a collision only if a safe regular destination
                # now exists; a genuine permission error without one remains 503.
                collision = isinstance(error, FileExistsError) or (
                    os.name == "nt" and getattr(error, "winerror", None) in (5, 32, 33)
                )
                if collision and self._target(inspection_id).is_file():
                    raise AppError("image_already_exists", "The inspection image already exists.", 409) from None
                raise
        except OSError:
            raise _storage_error() from None
        finally:
            if created_temporary:
                try:
                    self._target(inspection_id)
                    temporary.unlink(missing_ok=True)
                except OSError:
                    raise _storage_error() from None

    def path(self, inspection_id: str) -> Path:
        target = self._target(inspection_id, lookup=True)
        try:
            if not target.is_file():
                raise AppError("image_not_found", "The inspection image was not found.", 404)
            return target
        except OSError:
            raise _storage_error() from None

    def delete(self, inspection_id: str) -> None:
        target = self._target(inspection_id)
        try:
            target.unlink(missing_ok=True)
        except OSError:
            raise _storage_error() from None
