"""Shared wire types; validation does not implement project business rules."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator, AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field,
    StringConstraints,
)


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


NonEmptyString = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)
]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Latitude = Annotated[FiniteNumber, Field(ge=-90, le=90)]
Longitude = Annotated[FiniteNumber, Field(ge=-180, le=180)]
DemoFlag = Annotated[bool, Field(strict=True)]


def _timestamp_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("timestamp must be an aware ISO 8601 string or datetime")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp string must use ISO 8601, not a numeric timestamp") from exc
    return value


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


UTCTimestamp = Annotated[
    AwareDatetime, BeforeValidator(_timestamp_input), AfterValidator(_utc)
]


def _load_labels() -> dict[int, str]:
    path = Path(__file__).resolve().parents[3] / "model" / "label_schema.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    classes = source["classes"]
    mapping = {item["class_id"]: item["label_key"] for item in classes}
    if (
        len(classes) != 8
        or set(mapping) != set(range(8))
        or any(type(item["class_id"]) is not int for item in classes)
        or any(not isinstance(label, str) or not label.strip() for label in mapping.values())
        or len(set(mapping.values())) != 8
    ):
        raise ValueError("central label schema must contain eight distinct classes 0..7")
    return mapping


LABELS_BY_ID = _load_labels()
LABEL_KEYS = frozenset(LABELS_BY_ID.values())


def validate_json_metadata(value: object) -> object:
    """Reject non-JSON objects; producers must remove sensitive data before calling."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is list:
        for item in value:
            validate_json_metadata(item)
        return value
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            validate_json_metadata(item)
        return value
    raise ValueError("details must contain only finite JSON values and string object keys")
