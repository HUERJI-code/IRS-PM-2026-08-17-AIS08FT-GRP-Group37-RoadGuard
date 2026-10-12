"""Explicit demonstration assumptions; no production engineering defaults."""

from collections.abc import Mapping
import json
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer, model_validator

from roadguard.config import ConfigurationError
from roadguard.schemas.assessment import DemoOnly, ServiceMinutes
from roadguard.schemas.common import FiniteNumber, LABEL_KEYS, NonEmptyString


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    severity: Literal["low", "medium", "high"]
    priority: Literal["P1", "P2", "P3"]
    service_minutes: ServiceMinutes
    recommendation: NonEmptyString
    reason: NonEmptyString


class RulePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    rule_version: NonEmptyString
    is_demo: DemoOnly
    status: Literal["demonstration_assumptions"]
    confidence_threshold: Annotated[FiniteNumber, Field(ge=0, le=1)]
    selection_strategy: Literal["priority_severity_duration_confidence_id"]
    rules: Mapping[str, RuleDefinition]

    @model_validator(mode="after")
    def freeze_and_validate_mapping(self) -> Self:
        if set(self.rules) != LABEL_KEYS:
            raise ValueError("rules must contain exactly the eight central label keys")
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))
        return self

    @field_serializer("rules")
    def serialize_rules(self, rules: Mapping[str, RuleDefinition]) -> dict:
        return {key: rule.model_dump(mode="json") for key, rule in rules.items()}


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON value")


def load_rule_policy(path: Path) -> RulePolicy:
    """Fail safely for unreadable, malformed, incomplete or non-demo policies."""
    try:
        source = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        return RulePolicy.model_validate(source)
    except (OSError, UnicodeError, ValueError, TypeError, ValidationError):
        raise ConfigurationError("Demo rule policy could not be loaded or validated.") from None
