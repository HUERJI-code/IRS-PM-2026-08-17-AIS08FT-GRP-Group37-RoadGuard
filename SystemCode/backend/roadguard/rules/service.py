"""Deterministic candidate selection, with no I/O or task mutation."""

from collections.abc import Sequence

from pydantic import ValidationError

from roadguard.errors import AppError
from roadguard.schemas import DecisionTrace, Detection, RuleAssessment, RuleCandidate

from .policy import RulePolicy


PRIORITY_ORDER = {"P1": 0, "P2": 1, "P3": 2}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class RuleService:
    def __init__(self, policy: RulePolicy) -> None:
        # Revalidate even constructed/copied Pydantic objects, not only source JSON.
        self._policy = RulePolicy.model_validate(policy.model_dump(warnings=False))

    @property
    def policy(self) -> RulePolicy:
        return self._policy

    def _trace(self, code: str, message: str) -> DecisionTrace:
        return DecisionTrace(code=code, message=message, rule_version=self.policy.rule_version, is_demo=True)

    def _selection_key(self, detection: Detection) -> tuple:
        rule = self.policy.rules[detection.label]
        minutes = rule.service_minutes
        return (
            PRIORITY_ORDER[rule.priority],
            SEVERITY_ORDER[rule.severity],
            minutes is None,
            -minutes if minutes is not None else 0,
            -detection.confidence,
            detection.detection_id,
        )

    def evaluate(self, detections: Sequence[Detection]) -> RuleAssessment:
        try:
            # Mutated DTOs can trigger serializer warnings containing raw input.
            # Revalidation below rejects them; suppress only the serialization warning.
            snapshots = [Detection.model_validate(item.model_dump(warnings=False)) for item in detections]
            ids = [item.detection_id for item in snapshots]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate detection IDs")
            if len({(item.image_width, item.image_height) for item in snapshots}) > 1:
                raise ValueError("inconsistent original image dimensions")
        except (AttributeError, TypeError, ValueError, ValidationError):
            raise AppError("invalid_detections", "Detection input is invalid.", 422) from None

        trace = [self._trace(
            "demo_assumptions",
            "Demo-only project assumptions: confidence threshold, severity, priority and service time "
            "are not engineering measurements or validated production rules.",
        )]
        status = "no_detection"
        selected = None
        candidate = None
        if not snapshots:
            trace.append(self._trace("no_detection", "No detections; no task candidate is produced."))
        elif any(item.confidence < self.policy.confidence_threshold for item in snapshots):
            status = "pending_review"
            trace.append(self._trace(
                "confidence_review_required",
                f"At least one confidence is below the demo threshold {self.policy.confidence_threshold:g}; "
                "all detections remain available for review and no candidate is produced.",
            ))
        else:
            status = "ready_for_task"
            trace.append(self._trace(
                "confidence_gate_passed",
                f"All confidences meet or exceed the demo threshold {self.policy.confidence_threshold:g}.",
            ))
            for item in sorted(snapshots, key=lambda detection: detection.detection_id):
                rule = self.policy.rules[item.label]
                trace.append(self._trace("rule_mapping", f"{item.detection_id} ({item.label}): {rule.reason}"))
            selected = min(snapshots, key=self._selection_key)
            rule = self.policy.rules[selected.label]
            candidate = RuleCandidate(
                detection_id=selected.detection_id,
                damage_label=selected.label,
                severity=rule.severity,
                priority=rule.priority,
                service_minutes=rule.service_minutes,
                repair_recommendation=rule.recommendation,
                rule_version=self.policy.rule_version,
                is_demo=True,
            )
            trace.append(self._trace(
                "candidate_selected",
                "Choose one demo candidate by P1/P2/P3 priority, high/medium/low severity, "
                "longest known service time (unknown last), highest confidence, then ascending detection_id. "
                "This assessment does not create or accept a task.",
            ))
        return RuleAssessment(
            status=status,
            detections=snapshots,
            selected_detection_id=selected.detection_id if selected is not None else None,
            candidate=candidate,
            decision_trace=trace,
            rule_version=self.policy.rule_version,
            is_demo=True,
        )
