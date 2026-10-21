"""Read-only grounded summaries with separately validated source selections."""
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator
from roadguard.schemas.common import ContractModel
from .models import KnowledgeSource, Version

PlanID = Annotated[str, StringConstraints(strict=True, pattern=r'^plan-[0-9a-f]{32}$')]


class AssistantQuery(ContractModel):
    question: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=2, max_length=500)]
    scope: Literal['knowledge', 'plan']
    plan_id: PlanID | None = None
    rule_version: Version | None = None

    @model_validator(mode='after')
    def check_scope(self) -> Self:
        if (self.scope == 'plan') != (self.plan_id is not None):
            raise ValueError('plan scope requires plan_id; knowledge scope must omit it')
        return self


class AnswerSource(ContractModel):
    citation_id: str
    kind: Literal['knowledge', 'saved_plan']
    title: str
    classification: str
    content: str
    version: str
    sha256: str
    provenance: list[KnowledgeSource]


class EvidenceSelection(ContractModel):
    citation_id: Annotated[str, Field(min_length=1, max_length=200)]
    quote: Annotated[str, Field(min_length=1, max_length=2400)]


class ModelSelection(ContractModel):
    supported: bool
    # Six model-selected units may each carry one mandatory verbatim context.
    selections: Annotated[list[EvidenceSelection], Field(max_length=12)]
    answer: Annotated[str, Field(max_length=1800)] = ''


class ModelEvidenceIDs(ContractModel):
    supported: bool
    evidence_ids: Annotated[list[Annotated[str, Field(min_length=1, max_length=20)]], Field(max_length=6)]
    answer: Annotated[str, Field(max_length=1800)]


class PlanEvidenceSummary(ContractModel):
    plan_id: str
    input_revision: int
    algorithm: Literal['ga', 'greedy']
    matrix_provider: str
    matrix_is_simulated: bool
    is_demo: bool
    is_stale: bool


class AssistantAnswer(ContractModel):
    contract_version: Literal['c-assistant-query-v3'] = 'c-assistant-query-v3'
    status: Literal['supported', 'insufficient_data', 'rule_version_unavailable', 'stale_plan', 'model_refused', 'model_info', 'out_of_scope']
    supported: bool
    answer: str
    selections: list[EvidenceSelection]
    sources: list[AnswerSource]
    package_version: str | None
    manifest_sha256: str | None
    plan: PlanEvidenceSummary | None
    model: str | None
    model_called: bool
    answer_mode: Literal['grounded_summary', 'server_configuration', 'scope_guidance'] = 'grounded_summary'
    business_changes_applied: Literal[False] = False
    warnings: list[str]


class AssistantStatus(ContractModel):
    enabled: bool
    configured: bool
    model: str | None
    max_output_tokens: int
    max_calls_per_process: int
    calls_used: int
    read_only: Literal[True] = True
