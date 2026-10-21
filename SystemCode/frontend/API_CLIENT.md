# C step 3: API client and mock data

All implementation is within the frontend and does not change A/B APIs or databases. Coverage includes implemented health, demo, inspection, review, task, crew and route endpoints. The four assistant endpoints remain proposals and are not treated as existing APIs.

## Types and runtime validation

- `src/api/generated/openapi.json`: snapshot exported from the current FastAPI app.
- `src/api/generated/schema.d.ts`: complete openapi-typescript generated types; business code uses aliases such as `Model<'TaskRecord'>`.
- `src/api/contracts.ts`: validates every JSON response against the snapshot’s JSON Schemas, without numeric coercion, default insertion or unknown-field removal. HTML fallbacks, missing fields and wrong types fail explicitly.
- Multipart metadata is not expanded in backend OpenAPI. `UploadMetadata` is manually defined from current Python schemas: real forbids scenario_id; demo requires it. Images use a separate URL validator.
- JSON Schema does not include every Pydantic cross-field business check. Priority, rules, review and route validity remain backend responsibilities; frontend does not duplicate algorithms.

Maintain the snapshot from the frontend directory using a Python environment with backend requirements-ci.txt:

```sh
python scripts/export_contract.py --check
# Only when the backend contract has changed and the snapshot should be updated:
python scripts/export_contract.py
npm run api:types
npm run test:ci
npm run build
```

The exporter uses the existing application factory with an isolated temporary database, explicit demo detection and simulated travel matrix. It does not access the real project database or paid APIs and removes its temporary database afterwards. `--check` only compares current backend OpenAPI; it does not generate examples or run planning. Provenance is recorded in provenance.json. Regeneration changes random example IDs, timestamps and algorithm runtimes; examples are not experimental results. Never edit generated types manually to conceal backend changes.

Added dependencies: ajv/ajv-formats validate JSON Schema; openapi-typescript generates types. The generator requires TypeScript 5.x, so step 2’s 6.0.3 was changed to 5.9.3 to satisfy peer dependencies without forced installation. Node 22, npm and the single package-lock are unchanged.

## Calling from pages

Inside ApiProvider, `useApi()` returns `api`, `mode` and `imageUrl`. Live mode uses `/api/v1` through the development proxy, without page-specific backend hosts. The client has 16 JSON methods; imageUrl resolves the seventeenth endpoint for image loading.

| Domain | Methods |
|---|---|
| Foundation/demo | health, demoScenarios, demoAssessment |
| Inspection | upload, inspections, inspection, review |
| Task | tasks, snapshot, task, updateTask |
| Crew | crews, updateCrew |
| Plan | recalculate, latestPlan, plan |

Every method supports AbortSignal. Source changes cancel old reads and clear displayed data to prevent mixing sources. Default timeout is eight seconds; upload overrides this to 120 seconds. Larger real recalculations may use a longer configured timeoutMs, but automatic retry must not conceal timeouts. Upload sends image + metadata unchanged without manually constructing multipart Content-Type boundaries. Image URLs accept only same-origin `/api/v1/inspections/{32-character hex}/image`.

## Idempotency, revisions and errors

Create and retain one `createOperation(payload)` for review/task/crew changes. Its requestId and payload copy are fixed; retries reuse the same object. Content changes or refreshing/reconfirming a new record version create a new operation. Upload callers similarly retain the image, metadata and one request key rather than regenerating keys on retry.

`expected_version` identifies a record revision; `expected_revision` identifies the global planning-input revision. The client never updates stale versions automatically, silently replays old intent or automatically retries. B’s recalculation has no idempotency key: check results after timeout/network loss before any new calculation.

ApiError retains code, status, kind, details and outcomeUnknown. User messages map by code rather than matching backend message text. A write followed by network loss, timeout or malformed response has an uncertain outcome; the frontend cannot assert that it did not happen. Shared components distinguish loading, empty lists, no plan and errors. Explicit cancellation before submission does not mark an unknown write outcome.

Times use Asia/Singapore and English Singapore formatting. Timezone-free strings are rejected as invalid. Stop minute offsets are added to planning_start_at. formatMinutes and formatRuntime use minutes and milliseconds respectively; null/undefined means “Not provided”, while zero remains zero.

## Explicit mock modes

“Data source” offers live backend, normal mock, empty mock, service failure and revision conflict. Refresh resets to live mode; mock selection is not persisted and forgotten. Mock mode always shows provenance and never describes mock health as a real database connection.

Open “Check data connection” and click “Read current source” to inspect active-task count and GA plan availability. Only explicit action requests tasks/plans; navigation performs no writes.

- Normal: backend-generated accepted, pending_review and no_detection inspections; one active task, four crews and saved same-run GA/Greedy plans.
- Empty: no inspections/tasks, four configured crews and no saved plan. Missing plans return route_plan_not_found rather than a fabricated empty RoutePlan.
- Failure/conflict: structured 503 database_unavailable / 409 stale_input_revision.
- Mock reads support status filters, pagination and IDs; inconsistent snapshot revisions return conflicts.
- **Examples are fixed and read-only, not a writable mock backend.** POST/PATCH return local mock_write_unavailable, never claim success and never forward silently to real services. Future full upload/review demonstrations require explicit isolated scenarios rather than browser copies of A/B algorithms.
- Mock images are generated solid-colour PNGs, not road photos or model evidence. Mock server-image paths map to this image without reading real records.

## Validation boundary

Automated checks cover example schemas, request paths/fields, multipart, request-ID reuse, revision conflict, absence of automatic retry, timeout/cancellation, malformed responses, image URLs, pagination, explicit source switching, blocked mock writes, units and timezones. Step 4 adds real upload/details (UPLOAD_GUIDE.md); step 5 adds review (REVIEW_GUIDE.md); steps 6–7 implement task editing and crew controls, with explicit recalculation and revision checks (TASK_GUIDE.md, PLANNING_GUIDE.md). This does not claim complete dispatch end-to-end acceptance.

## Assistant retrieval, evidence answers and crew changes (2026-10-21)

The dispatcher-only assistant uses the existing session, role and CSRF checks:

- `POST /api/v1/assistant/knowledge/search` returns versioned static passages, stable citations and source integrity metadata; it does not generate answers or read business plans. Rule-version mismatch returns empty hits; inconsistent knowledge returns `503 knowledge_unavailable`.
- `GET /api/v1/assistant/status` exposes non-secret configuration status. `POST /api/v1/assistant/query` accepts question, scope and optional plan_id/rule_version. Plan questions require an explicit saved plan loaded through B's query service. `c-assistant-query-v1` returns verified evidence extracts and provenance without business changes. Real GPT connectivity and semantic quality remain unverified.
- `/api/v1/assistant/change-requests` provides preview/history and per-request confirm/cancel/replan operations under `c-assistant-change-v1`. Preview does not change planning input. Confirmation and recalculation are separate explicit actions; history supports uncertain-outcome recovery. This flow does not call GPT.

Schema v5 adds persistent assistant change requests and audit records while retaining v4 accounts, sessions, ownership, crews and plans. No new dependency or model weight is required. The assistant guide defines limits, concurrency, idempotency, failure handling and server-only provider configuration.

Client methods knowledgeSearch, assistantStatus and assistantQuery use the shared schema validation. Read-only POST failures do not imply an unknown business mutation; provider usage may still occur after cancellation. Questions wait at most 60 seconds, with no automatic retry. Mock mode blocks provider calls and business changes. Change previews, confirmation, cancellation and explicit replanning use the independent ChangePanel and persisted history.
