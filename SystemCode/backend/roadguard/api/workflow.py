"""HTTP adapters for the persisted inspection, review and task workflow."""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Path, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import ValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from roadguard.errors import AppError
from roadguard.images import MAX_UPLOAD_BYTES
from roadguard.inspections import WorkflowService
from roadguard.schemas import ErrorResponse
from roadguard.schemas.task_query import TaskSnapshot
from roadguard.schemas.workflow import (
    InspectionListResponse, InspectionMutationResponse, InspectionResponse, InspectionUploadResponse, ReviewRequest,
    TaskList, TaskMutation, TaskPatch, TaskRecord, UploadMetadata,
)


router = APIRouter()
ResourceID = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]
InspectionStatus = Literal["no_detection", "pending_review", "accepted", "rejected", "all"]
TaskStatus = Literal["active", "completed", "cancelled", "all"]
ERRORS = {code: {"model": ErrorResponse} for code in (404, 409, 422, 503)}
MAX_BODY_BYTES = MAX_UPLOAD_BYTES + 64 * 1024
MAX_METADATA_BYTES = 16 * 1024


def _service(request: Request) -> WorkflowService:
    service = getattr(request.app.state, "workflow_service", None)
    if service is None:
        raise AppError("workflow_unavailable", "The inspection workflow is unavailable.", 503)
    return service


def _unique_json(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata field")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Invalid JSON number")


async def _upload(request: Request) -> tuple[UploadMetadata, bytes]:
    """Bound the stream before parsing multipart or creating temporary files."""
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "multipart/form-data":
        raise AppError("unsupported_upload_type", "Use multipart/form-data with image and metadata.", 415)
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise AppError("image_too_large", "The upload exceeds the allowed size.", 413)
        body.extend(chunk)

    async def receive() -> dict:
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    # Use public Request APIs; the original stream has already been bounded.
    parsed = Request(request.scope, receive=receive)
    try:
        async with parsed.form(max_files=1, max_fields=1, max_part_size=MAX_METADATA_BYTES) as form:
            fields = form.multi_items()
            if len(fields) != 2 or {name for name, _ in fields} != {"image", "metadata"}:
                raise ValueError("Expected exactly one image and one metadata field")
            image, metadata = form["image"], form["metadata"]
            if not isinstance(image, UploadFile) or not isinstance(metadata, str):
                raise ValueError("Invalid field types")
            if len(metadata.encode("utf-8")) > MAX_METADATA_BYTES:
                raise ValueError("Metadata too large")
            payload = UploadMetadata.model_validate(json.loads(
                metadata, object_pairs_hook=_unique_json, parse_constant=_invalid_constant,
            ))
            data = await image.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise AppError("image_too_large", "The image exceeds the allowed size.", 413)
            return payload, data
    except (ValueError, ValidationError, UnicodeError, HTTPException, MultipartParseError):
        raise AppError("validation_error", "Upload fields are invalid.", 422) from None
    except OSError:
        raise AppError("image_storage_unavailable", "Upload storage is unavailable.", 503) from None


@router.post(
    "/inspections", response_model=InspectionUploadResponse, status_code=201, tags=["Inspections"],
    responses={**ERRORS, 200: {"model": InspectionUploadResponse}, 413: {"model": ErrorResponse},
               415: {"model": ErrorResponse}, 502: {"model": ErrorResponse}},
    summary="Upload an image, return one primary box and automatically create an eligible task",
    description="Returns inspection_id, status, detection and task_id only. Read the inspection detail endpoint for provenance and review fields. New uploads return 201; idempotent replays return 200.",
    openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {
        "schema": {"type": "object", "required": ["image", "metadata"], "properties": {
            "image": {"type": "string", "format": "binary", "description": "One JPEG or PNG, at most 8 MiB and 20 megapixels."},
            "metadata": {"type": "string", "description": "JSON UploadMetadata; road type is a user declaration, not a verified road classification.",
                         "example": '{"mode":"real","latitude":1.3405,"longitude":103.706,"road_type":"public_motor_road"}'},
        }},
    }}}},
)
async def create_inspection(
    request: Request, response: Response,
    idempotency_key: Annotated[str, Header(pattern=r"^[A-Za-z0-9_-]{1,64}$")],
) -> InspectionUploadResponse:
    service = _service(request)
    metadata, data = await _upload(request)
    image = await run_in_threadpool(service.images.prepare, data)
    result = await run_in_threadpool(service.create, metadata, image, idempotency_key, actor=request.state.account)
    response.status_code = 200 if result.replayed else 201
    return InspectionUploadResponse.from_record(result.inspection)


@router.get("/inspections", response_model=InspectionListResponse, responses=ERRORS, tags=["Inspections"])
def list_inspections(request: Request, status: InspectionStatus = "all", limit: PageLimit = 50,
                     offset: PageOffset = 0) -> InspectionListResponse:
    return InspectionListResponse.from_result(
        _service(request).list_inspections(status=None if status == "all" else status, limit=limit, offset=offset))


@router.get("/inspections/{inspection_id}", response_model=InspectionResponse, responses=ERRORS, tags=["Inspections"])
def get_inspection(request: Request, inspection_id: ResourceID) -> InspectionResponse:
    return InspectionResponse.from_record(_service(request).get_inspection(inspection_id, actor=request.state.account))


@router.get("/inspections/{inspection_id}/image", response_class=FileResponse,
            responses={**ERRORS, 200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
            tags=["Inspections"])
def get_inspection_image(request: Request, inspection_id: ResourceID) -> FileResponse:
    service = _service(request)
    service.get_inspection(inspection_id, actor=request.state.account)
    return FileResponse(service.images.path(inspection_id), media_type="image/png",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.post("/inspections/{inspection_id}/review", response_model=InspectionMutationResponse,
             responses=ERRORS, tags=["Inspections"])
def review_inspection(request: Request, inspection_id: ResourceID, payload: ReviewRequest) -> InspectionMutationResponse:
    return InspectionMutationResponse.from_result(_service(request).review(inspection_id, payload, actor=request.state.account))


@router.get("/tasks", response_model=TaskList, responses=ERRORS, tags=["Tasks"])
def list_tasks(request: Request, status: TaskStatus = "active", limit: PageLimit = 50,
               offset: PageOffset = 0) -> TaskList:
    return _service(request).list_tasks(status=None if status == "all" else status, limit=limit, offset=offset)


@router.get("/tasks/snapshot", response_model=TaskSnapshot, responses=ERRORS, tags=["Tasks"],
            summary="Read every active task and the shared revision in one snapshot")
def get_task_snapshot(
    request: Request, expected_revision: Annotated[int | None, Query(ge=0)] = None,
) -> TaskSnapshot:
    service = getattr(request.app.state, "task_query_service", None)
    if service is None:
        raise AppError("task_query_unavailable", "The task query service is unavailable.", 503)
    return service.snapshot(expected_revision)


@router.get("/tasks/{task_id}", response_model=TaskRecord, responses=ERRORS, tags=["Tasks"])
def get_task(request: Request, task_id: ResourceID) -> TaskRecord:
    return _service(request).get_task(task_id, actor=request.state.account)


@router.patch("/tasks/{task_id}", response_model=TaskMutation, responses=ERRORS, tags=["Tasks"])
def update_task(request: Request, task_id: ResourceID, payload: TaskPatch) -> TaskMutation:
    return _service(request).update_task(task_id, payload, actor=request.state.account)
