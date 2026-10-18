from typing import Annotated, Literal

from pydantic import Field, SecretStr

from roadguard.schemas.common import ContractModel
from roadguard.crews.schemas import CrewRecord
from roadguard.routing.models import CrewRoute, Depot, PlanningSettings
from roadguard.schemas.common import UTCTimestamp
from roadguard.schemas.workflow import TaskRecord

Role = Literal["inspector", "crew", "dispatcher"]


class Account(ContractModel):
    user_id: str
    username: str
    display_name: str
    role: Role
    crew_id: str | None


class LoginRequest(ContractModel):
    username: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")]
    password: SecretStr = Field(min_length=1, max_length=256)


class SessionResponse(ContractModel):
    user: Account
    csrf_token: str
    expires_at: int


class LogoutResponse(ContractModel):
    logged_out: Literal[True] = True


class CrewWorkspacePlan(ContractModel):
    """Only the account's crew route; no other crews, matrix or global metrics."""
    plan_id: str
    algorithm: Literal["ga"]
    input_revision: int
    is_stale: bool
    planning_start_at: UTCTimestamp
    depot: Depot
    settings: PlanningSettings
    matrix_provider: str
    matrix_is_simulated: bool
    crew_routes: list[CrewRoute]


class CrewWorkspaceResponse(ContractModel):
    crew: CrewRecord
    plan: CrewWorkspacePlan | None
    tasks: list[TaskRecord]
    input_revision: int
