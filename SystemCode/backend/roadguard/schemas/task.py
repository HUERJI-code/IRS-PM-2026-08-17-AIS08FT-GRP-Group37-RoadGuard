"""Task output vocabulary; label-to-business-rule mapping remains unimplemented."""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from .common import (
    ContractModel, DemoFlag, FiniteNumber, LABEL_KEYS, Latitude, Longitude,
    NonEmptyString, UTCTimestamp,
)


class Task(ContractModel):
    task_id: NonEmptyString
    inspection_id: NonEmptyString
    latitude: Latitude
    longitude: Longitude
    damage_label: NonEmptyString
    severity: Literal["low", "medium", "high"]
    priority: Literal["P1", "P2", "P3"]
    service_minutes: Annotated[FiniteNumber, Field(gt=0)] | None
    created_at: UTCTimestamp
    due_at: UTCTimestamp | None
    status: Literal["active", "completed", "cancelled"]
    rule_version: NonEmptyString
    is_demo: DemoFlag

    @field_validator("damage_label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        if value not in LABEL_KEYS:
            raise ValueError("damage_label must be a central RDD2022ES label_key")
        return value
