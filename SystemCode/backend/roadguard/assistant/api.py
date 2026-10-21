"""Read-only search uses POST to keep question text out of URL query logs."""
from typing import Annotated
from fastapi import Path
from .change_models import ChangePreview, ChangeConfirm, ChangeReplan, ChangeRecord, ChangeList
from .change_service import ChangeService
from fastapi import APIRouter, Request
from roadguard.errors import AppError
from roadguard.schemas import ErrorResponse

from .knowledge import KnowledgeIntegrityError, load_package
from .models import KnowledgeSearchRequest, KnowledgeSearchResponse
from .retrieval import search
from .query_models import AssistantQuery, AssistantAnswer, AssistantStatus
from .query_service import answer_query
from .provider import config_from_env, BUDGET

router = APIRouter(tags=['Knowledge retrieval'])


@router.post('/assistant/knowledge/search', response_model=KnowledgeSearchResponse,
             responses={code: {'model': ErrorResponse} for code in (401, 403, 422, 503)},
             summary='Retrieve verified static knowledge sections (dispatcher only)',
             description='Read-only local E5 embeddings and Chroma cosine retrieval. '
                         'Requires session cookie and CSRF token. Incompatible rule versions return no hits.')
def search_knowledge(payload: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    try:
        return search(load_package(), payload)
    except KnowledgeIntegrityError as exc:
        raise AppError('knowledge_unavailable', 'The knowledge package could not be verified.', 503) from exc


@router.get('/assistant/status', response_model=AssistantStatus,
            responses={503: {'model': ErrorResponse}})
def assistant_status() -> AssistantStatus:
    config = config_from_env()
    return AssistantStatus(enabled=config.enabled, configured=config.configured,
                           model=config.model or None, max_output_tokens=config.max_output_tokens,
                           max_calls_per_process=config.max_calls, calls_used=BUDGET.used)


@router.post('/assistant/query', response_model=AssistantAnswer,
             responses={code: {'model': ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 502, 503)},
             summary='Read-only evidence-selected GPT answer; dispatcher session and CSRF required')
def query_assistant(request: Request, payload: AssistantQuery) -> AssistantAnswer:
    try:
        return answer_query(payload, request.state.account.user_id, request.app.state.route_query_service)
    except KnowledgeIntegrityError:
        raise AppError('knowledge_unavailable', 'The knowledge package could not be verified.', 503) from None



ChangePath = Annotated[str, Path(pattern=r"^change-[0-9a-f]{32}$")]
CHANGE_ERRORS = {code: {"model": ErrorResponse} for code in (404, 409, 422, 503)}


def changes(request: Request) -> ChangeService:
    state = request.app.state
    return ChangeService(state.database, state.crew_service, state.route_query_service, state.planning_service)


@router.get('/assistant/change-requests', response_model=ChangeList, responses=CHANGE_ERRORS)
def list_changes(request: Request):
    return changes(request).list(request.state.account.user_id)


@router.post('/assistant/change-requests', response_model=ChangeRecord, responses=CHANGE_ERRORS)
def preview_change(request: Request, payload: ChangePreview):
    return changes(request).preview(payload, request.state.account.user_id)


@router.get('/assistant/change-requests/{change_id}', response_model=ChangeRecord, responses=CHANGE_ERRORS)
def get_change(request: Request, change_id: ChangePath):
    return changes(request).get(change_id, request.state.account.user_id)


@router.post('/assistant/change-requests/{change_id}/confirm', response_model=ChangeRecord, responses=CHANGE_ERRORS)
def confirm_change(request: Request, change_id: ChangePath, payload: ChangeConfirm):
    return changes(request).confirm(change_id, request.state.account.user_id, payload.expected_version)


@router.post('/assistant/change-requests/{change_id}/cancel', response_model=ChangeRecord, responses=CHANGE_ERRORS)
def cancel_change(request: Request, change_id: ChangePath, payload: ChangeConfirm):
    return changes(request).cancel(change_id, request.state.account.user_id, payload.expected_version)


@router.post('/assistant/change-requests/{change_id}/replan', response_model=ChangeRecord, responses=CHANGE_ERRORS)
def replan_change(request: Request, change_id: ChangePath, payload: ChangeReplan):
    return changes(request).replan(change_id, request.state.account.user_id, payload.attempt_id)
