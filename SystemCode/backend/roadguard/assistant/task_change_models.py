from typing import Annotated, Literal
from pydantic import Field, StringConstraints, model_validator
from roadguard.schemas.common import ContractModel, NonNegativeInt, PositiveInt, UTCTimestamp
from roadguard.schemas.workflow import RequestId
from roadguard.routing.models import CrewRoute
from roadguard.routing.service import RecalculationResult
from .query_models import PlanID

TaskChangeID = Annotated[str, StringConstraints(strict=True, pattern=r"^task-change-[0-9a-f]{32}$")]


class TaskChangePreview(ContractModel):
    request_id: RequestId
    based_on_plan_id: PlanID
    action: Literal["reassign", "cancel_task"]
    task_id: str = Field(min_length=1, max_length=100)
    target_crew_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def target(self):
        if (self.action == "reassign") != (self.target_crew_id is not None):
            raise ValueError("Only reassignment requires target_crew_id.")
        return self


class TaskChangeRecord(ContractModel):
    contract_version: Literal["c-assistant-task-change-v1"] = "c-assistant-task-change-v1"
    change_id: TaskChangeID
    actor_id: str
    client_key: RequestId
    based_on_plan_id: PlanID
    input_revision: NonNegativeInt
    action: Literal["reassign", "cancel_task"]
    task_id: str
    task_record_version: PositiveInt
    planning_config_fingerprint: str
    source_crew_id: str | None
    target_crew_id: str | None = None
    status: Literal["pending", "confirmed", "cancelled", "expired"]
    record_version: PositiveInt
    created_at: UTCTimestamp
    expires_at: UTCTimestamp
    applied_revision: NonNegativeInt | None = None
    before_routes: list[CrewRoute]
    after_routes: list[CrewRoute]
    shift_limit_minutes: float | None
    return_to_depot: bool
    replan_status: Literal["not_requested", "running", "failed", "succeeded"] = "not_requested"
    replan_attempts: list[RequestId] = Field(default_factory=list)
    replan_attempt_id: RequestId | None = None
    replan_lease_until: UTCTimestamp | None = None
    replan_error_code: str | None = None
    result: RecalculationResult | None = None


class TaskChangeList(ContractModel):
    items: list[TaskChangeRecord]
