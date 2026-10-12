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
        "演示：单个高置信度坑洞；固定合成结果，不读取图片。",
        ((6, 0.96, (120, 90, 340, 260)),),
    ),
    "low_confidence": _Scenario(
        "演示：单个低置信度坑洞，供人工复核分流测试。",
        ((6, 0.42, (120, 90, 340, 260)),),
    ),
    "no_detection": _Scenario(
        "演示：没有检测结果，不代表实际图片未发现损坏。",
        (),
    ),
    "multiple_detections": _Scenario(
        "演示：纵向裂缝 0.98 与深坑洞 0.90，用于验证业务选取不只看最高置信度。",
        ((0, 0.98, (60, 60, 180, 300)), (7, 0.90, (320, 200, 540, 400))),
    ),
    "mixed_confidence": _Scenario(
        "演示：高置信度坑洞与低置信度深坑洞，供整次巡检待复核测试。",
        ((6, 0.96, (60, 60, 250, 220)), (7, 0.42, (320, 200, 540, 400))),
    ),
    "threshold_boundary": _Scenario(
        "演示：置信度恰好为演示阈值候选 0.60；该值不是正式批准阈值。",
        ((6, 0.60, (120, 90, 340, 260)),),
    ),
    "below_threshold": _Scenario(
        "演示：置信度 0.5999，供演示阈值候选 0.60 下方的边界测试。",
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
