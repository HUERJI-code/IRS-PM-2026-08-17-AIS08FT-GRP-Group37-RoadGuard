"""Shared health, error and planning-revision response objects."""

from typing import Literal

from pydantic import JsonValue, field_validator

from .common import ContractModel, NonEmptyString, NonNegativeInt, validate_json_metadata


class ErrorResponse(ContractModel):
    code: NonEmptyString
    message: NonEmptyString
    details: list[JsonValue] | dict[str, JsonValue] | None = None

    @field_validator("details", mode="before")
    @classmethod
    def validate_details(cls, value: object) -> object:
        if value is not None and type(value) not in (dict, list):
            raise ValueError("details must be a JSON object, JSON array or null")
        return validate_json_metadata(value)


class PlanningRevision(ContractModel):
    input_revision: NonNegativeInt


class HealthResponse(PlanningRevision):
    status: Literal["ok"]
    database: Literal["ok"]
    api_version: Literal["v1"] = "v1"
