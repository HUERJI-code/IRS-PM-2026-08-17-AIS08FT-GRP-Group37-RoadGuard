"""Experimental single-subject suggestions; never an acceptance or probability gate."""

from dataclasses import dataclass
import math
from typing import Sequence

from roadguard.schemas import Detection


STRATEGIES = ("confidence", "area_quarter", "area_half", "centrality")
POLICY_VERSION = "single-damage-v1"


@dataclass(frozen=True)
class PrimaryPolicy:
    strategy: str
    threshold: float

    def __post_init__(self):
        if self.strategy not in STRATEGIES:
            raise ValueError("Unknown primary ranking strategy")
        if type(self.threshold) not in (int, float) or not math.isfinite(self.threshold) or not 0 < self.threshold <= 1:
            raise ValueError("Threshold must be finite and within (0, 1]")


def overlap(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union


def ranking_score(detection: Detection, strategy: str) -> float:
    left, top, right, bottom = detection.bbox_xyxy
    area = (right - left) * (bottom - top) / (detection.image_width * detection.image_height)
    if strategy == "confidence":
        factor = 1.0
    elif strategy in {"area_quarter", "area_half"}:
        factor = area ** (0.25 if strategy == "area_quarter" else 0.5)
    elif strategy == "centrality":
        distance = math.hypot((left + right) / detection.image_width - 1,
                              (top + bottom) / detection.image_height - 1) / math.sqrt(2)
        factor = 1 - 0.5 * distance
    else:
        raise ValueError("Unknown primary ranking strategy")
    return detection.confidence * factor


def suggest_primary(detections: Sequence[Detection], policy: PrimaryPolicy) -> dict:
    """Keep raw evidence outside this view. Ambiguity yields no preferred box.

    A competing class or disjoint region with >=80% of the first ranking score
    triggers review. Ranking scores are heuristics, not calibrated probabilities.
    This consistency gate is fixed before evaluation, not selected on test data.
    """
    if len(detections) > 100 or len({d.detection_id for d in detections}) != len(detections):
        raise ValueError("Expected at most 100 unique detections")
    if len({(d.image_width, d.image_height, d.model_version, d.is_demo) for d in detections}) > 1:
        raise ValueError("Detections must share image dimensions and model provenance")
    ranked = sorted(((ranking_score(d, policy.strategy), i, d) for i, d in enumerate(detections)
                     if d.confidence >= policy.threshold), key=lambda item: (-item[0], item[1]))
    result = {"policy_version": POLICY_VERSION, "strategy": policy.strategy, "threshold": policy.threshold,
              "status": "no_suggestion", "detection_id": None, "ranking_score": None,
              "competing_detection_ids": [], "reason": "no_candidate_above_filter"}
    if not ranked:
        return result
    score, _, first = ranked[0]
    rivals = [d.detection_id for other_score, _, d in ranked[1:]
              if other_score >= score * 0.8 and (d.class_id != first.class_id
                                               or overlap(d.bbox_xyxy, first.bbox_xyxy) < 0.1)]
    if rivals:
        result.update(status="ambiguous", competing_detection_ids=[first.detection_id, *rivals],
                      reason="competing_types_or_regions")
    else:
        result.update(status="suggested", detection_id=first.detection_id, ranking_score=score,
                      reason="single_main_subject_requires_review")
    return result
