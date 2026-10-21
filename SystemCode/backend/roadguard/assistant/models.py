"""C's read-only retrieval contract; retrieved text is evidence, never an answer."""
from typing import Annotated, Literal

from pydantic import Field, StringConstraints
from roadguard.schemas.common import ContractModel

Classification = Literal['confirmed_project_fact', 'demo_assumption', 'pending_decision']
Version = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)]


class KnowledgeSearchRequest(ContractModel):
    query: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=2, max_length=500)]
    limit: Annotated[int, Field(strict=True, ge=1, le=8)] = 5
    rule_version: Version | None = None


class KnowledgeSource(ContractModel):
    source_id: str
    path: str
    integrity: Literal['sha256_verified', 'unhashed_mutable_context']
    sha256: str | None = None
    version: str | None = None


class KnowledgeChunk(ContractModel):
    citation_id: str
    document_id: str
    section_id: str
    document_version: str
    document_sha256: str
    document_path: str
    title: str
    classification: Classification
    text: str
    sources: list[KnowledgeSource]


class KnowledgeHit(KnowledgeChunk):
    score: float
    matched_terms: list[str]


class KnowledgeSearchResponse(ContractModel):
    contract_version: Literal['c-knowledge-search-v1'] = 'c-knowledge-search-v1'
    status: Literal['matches', 'no_matches', 'rule_version_unavailable']
    package_id: str
    package_version: str
    manifest_sha256: str
    versions: dict[str, str]
    retrieval_method: Literal['lexical-zh-bigram-tfidf-v1'] = 'lexical-zh-bigram-tfidf-v1'
    evidence_scope: Literal['static_knowledge_only'] = 'static_knowledge_only'
    answer_generated: Literal[False] = False
    limitations: list[str]
    hits: list[KnowledgeHit]
