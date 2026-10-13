"""A frozen display suggestion, separate from the accepted task selection."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import ContractModel, FiniteNumber, NonEmptyString


class PrimarySuggestion(ContractModel):
    policy_version: Literal["single-damage-v1"]
    strategy: Literal["confidence", "area_quarter", "area_half", "centrality"]
    threshold: Annotated[FiniteNumber, Field(gt=0, le=1)]
    detection_id: NonEmptyString | None
    ranking_score: Annotated[FiniteNumber, Field(ge=0, le=1)] | None
    ambiguous: Annotated[bool, Field(strict=True)]
    competing_detection_ids: list[NonEmptyString]

    @model_validator(mode="after")
    def validate_suggestion(self) -> Self:
        if (self.detection_id is None) != (self.ranking_score is None):
            raise ValueError("suggestion ID and ranking score must both be present or absent")
        rivals = self.competing_detection_ids
        if len(rivals) != len(set(rivals)):
            raise ValueError("competing detection IDs must be unique")
        if self.ambiguous:
            if self.detection_id is None or len(rivals) < 2 or self.detection_id not in rivals:
                raise ValueError("ambiguity requires the suggested and competing detections")
        elif rivals:
            raise ValueError("unambiguous suggestions cannot contain competitors")
        return self
