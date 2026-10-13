"""Bridge the evaluated ranking policy into a persisted review-only suggestion."""

from roadguard.schemas.primary import PrimarySuggestion
from roadguard.vision.primary import POLICY_VERSION, PrimaryPolicy, ranking_score, suggest_primary


def primary_suggestion(detections, policy: PrimaryPolicy) -> PrimarySuggestion:
    warning = suggest_primary(detections, policy)
    eligible = [item for item in detections if item.confidence >= policy.threshold]
    selected = max(eligible, key=lambda item: ranking_score(item, policy.strategy), default=None)
    return PrimarySuggestion(
        policy_version=POLICY_VERSION, strategy=policy.strategy, threshold=policy.threshold,
        detection_id=selected.detection_id if selected else None,
        ranking_score=ranking_score(selected, policy.strategy) if selected else None,
        ambiguous=warning["status"] == "ambiguous", competing_detection_ids=warning["competing_detection_ids"],
    )
