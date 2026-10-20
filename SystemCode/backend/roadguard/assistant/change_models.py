from typing import Annotated, Literal
from pydantic import Field, StringConstraints
from roadguard.schemas.common import ContractModel, NonNegativeInt, PositiveInt, UTCTimestamp
from roadguard.schemas.workflow import RequestId
from roadguard.routing.service import RecalculationResult
from .query_models import PlanID

ChangeID = Annotated[str, StringConstraints(strict=True, pattern=r'^change-[0-9a-f]{32}$')]


class ChangePreview(ContractModel):
    request_id: RequestId
    based_on_plan_id: PlanID
    instruction: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=2, max_length=200)]


class ChangeConfirm(ContractModel):
    expected_version: PositiveInt


class ChangeReplan(ContractModel):
    attempt_id: RequestId


class ChangeRecord(ContractModel):
    contract_version: Literal['c-assistant-change-v1'] = 'c-assistant-change-v1'
    change_id: ChangeID
    actor_id: str
    client_key: RequestId
    instruction: str
    based_on_plan_id: PlanID
    input_revision: NonNegativeInt
    crew_id: str
    crew_record_version: PositiveInt
    before_available: bool
    after_available: bool
    status: Literal['pending', 'confirmed', 'cancelled', 'expired', 'failed']
    record_version: PositiveInt
    created_at: UTCTimestamp
    expires_at: UTCTimestamp
    confirmed_at: UTCTimestamp | None = None
    applied_revision: NonNegativeInt | None = None
    planning_input_changed: bool = False
    error_code: str | None = None
    replan_status: Literal['not_requested', 'running', 'failed', 'succeeded'] = 'not_requested'
    replan_attempts: list[RequestId] = Field(default_factory=list)
    replan_attempt_id: RequestId | None = None
    replan_lease_until: UTCTimestamp | None = None
    replan_error_code: str | None = None
    result: RecalculationResult | None = None
    warning: str = '预览不会改变队伍。确认只保存可用状态；重算须另行点击，失败不会自动撤销已保存的状态。'


class ChangeList(ContractModel):
    items: list[ChangeRecord]
