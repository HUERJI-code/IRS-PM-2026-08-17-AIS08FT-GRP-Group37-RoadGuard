"""B-owned crew wire models (b-crew-v1)."""

from typing import Literal

from roadguard.schemas.common import ContractModel, NonEmptyString, NonNegativeInt, PositiveInt, UTCTimestamp
from roadguard.schemas.workflow import RequestId


class CrewRecord(ContractModel):
    crew_id: NonEmptyString
    name: NonEmptyString
    available: bool
    depot_id: NonEmptyString
    record_version: PositiveInt
    updated_at: UTCTimestamp | None   # null: configured default, never changed


class CrewList(ContractModel):
    contract_version: Literal["b-crew-v1"] = "b-crew-v1"
    crews: list[CrewRecord]
    input_revision: NonNegativeInt


class CrewPatch(ContractModel):
    """Only availability is editable in the first version (assistant scope is the same)."""

    request_id: RequestId
    expected_version: PositiveInt
    available: bool


class CrewMutation(ContractModel):
    contract_version: Literal["b-crew-v1"] = "b-crew-v1"
    crew: CrewRecord
    input_revision: NonNegativeInt
    # True means existing plans are now stale; it does not mean a new plan was computed.
    planning_input_changed: bool
    replayed: bool
