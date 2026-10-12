"""Source-labelled detections in original-image pixel coordinates."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from .common import (
    ContractModel, DemoFlag, FiniteNumber, LABELS_BY_ID, NonEmptyString, PositiveInt,
)


class Detection(ContractModel):
    detection_id: NonEmptyString
    class_id: Annotated[int, Field(strict=True, ge=0, le=7)]
    label: NonEmptyString
    confidence: Annotated[FiniteNumber, Field(ge=0, le=1)]
    bbox_xyxy: tuple[FiniteNumber, FiniteNumber, FiniteNumber, FiniteNumber]
    image_width: PositiveInt
    image_height: PositiveInt
    model_version: NonEmptyString
    is_demo: DemoFlag

    @model_validator(mode="after")
    def validate_source_and_box(self) -> Self:
        if self.label != LABELS_BY_ID[self.class_id]:
            raise ValueError("label must match class_id in model/label_schema.json")
        left, top, right, bottom = self.bbox_xyxy
        if not (0 <= left < right <= self.image_width):
            raise ValueError("bbox x coordinates must have positive width within the image")
        if not (0 <= top < bottom <= self.image_height):
            raise ValueError("bbox y coordinates must have positive height within the image")
        return self
