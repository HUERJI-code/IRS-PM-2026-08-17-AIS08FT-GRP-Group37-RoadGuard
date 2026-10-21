"""Named synthetic detections for integration; this adapter does not inspect pixels."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, Mapping

from roadguard.schemas import Detection
from roadguard.schemas.common import LABELS_BY_ID


_Box = tuple[int, int, int, int]
_FixtureDetection = tuple[int, float, _Box]


@dataclass(frozen=True)
class _Scenario:
    description: str
    detections: tuple[_FixtureDetection, ...]


_SCENARIO_FIXTURES: Mapping[str, _Scenario] = MappingProxyType({
    "high_confidence": _Scenario(
        "Demo: one high-confidence pothole; fixed synthetic results, without reading the image.",
        ((6, 0.96, (120, 90, 340, 260)),),
    ),
    "low_confidence": _Scenario(
        "Demo: one low-confidence pothole for testing manual-review routing.",
        ((6, 0.42, (120, 90, 340, 260)),),
    ),
    "no_detection": _Scenario(
        "Demo: no detections; this does not establish that the actual image contains no damage.",
        (),
    ),
    "multiple_detections": _Scenario(
        "Demo: longitudinal crack at 0.98 and deep pothole at 0.90; verifies that business selection considers more than the highest confidence.",
        ((0, 0.98, (60, 60, 180, 300)), (7, 0.90, (320, 200, 540, 400))),
    ),
    "mixed_confidence": _Scenario(
        "Demo: a high-confidence pothole and a low-confidence deep pothole for testing review of the entire inspection.",
        ((6, 0.96, (60, 60, 250, 220)), (7, 0.42, (320, 200, 540, 400))),
    ),
    "threshold_boundary": _Scenario(
        "Demo: confidence exactly at the candidate demo threshold of 0.60; this is not a formally approved engineering threshold.",
        ((6, 0.60, (120, 90, 340, 260)),),
    ),
    "below_threshold": _Scenario(
        "Demo: confidence 0.5999 for testing the boundary below the candidate demo threshold of 0.60.",
        ((6, 0.5999, (120, 90, 340, 260)),),
    ),
})

# Expose descriptions without giving callers a mutable handle to fixture storage.
SCENARIOS: Mapping[str, str] = MappingProxyType({
    scenario_id: fixture.description
    for scenario_id, fixture in _SCENARIO_FIXTURES.items()
})


class DemoScenarioNotFound(ValueError):
    """A requested synthetic scenario is unsupported; do not echo caller input."""

    def __init__(self) -> None:
        super().__init__("The requested demo scenario is not available.")


class DemoDetector:
    """Deterministic fixture adapter; no model, image IO, network or persistence."""

    model_version: ClassVar[str] = "demo-detector-v1"
    is_demo: ClassVar[bool] = True
    image_width: ClassVar[int] = 640
    image_height: ClassVar[int] = 480

    def detect(self, scenario_id: str, *, image_width: int | None = None, image_height: int | None = None) -> list[Detection]:
        """Return fresh validated DTOs from a named case, not an uploaded image."""
        if not isinstance(scenario_id, str) or scenario_id not in _SCENARIO_FIXTURES:
            raise DemoScenarioNotFound()
        width = self.image_width if image_width is None else image_width
        height = self.image_height if image_height is None else image_height
        if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive integers.")
        fixture = _SCENARIO_FIXTURES[scenario_id]
        return [
            Detection(
                detection_id=f"demo-{scenario_id}-{index:02d}",
                class_id=class_id,
                label=LABELS_BY_ID[class_id],
                confidence=confidence,
                bbox_xyxy=(box[0] * width / self.image_width, box[1] * height / self.image_height,
                           box[2] * width / self.image_width, box[3] * height / self.image_height),
                image_width=width,
                image_height=height,
                model_version=self.model_version,
                is_demo=self.is_demo,
            )
            for index, (class_id, confidence, box) in enumerate(fixture.detections, start=1)
        ]
