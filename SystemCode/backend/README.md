# RoadGuard shared backend

See [released model installation and primary suggestions](../../Miscellaneous/MODEL_RELEASE_AND_BACKEND.md) for the current default detector and client migration.

Deployment weights are committed at `SystemCode/backend/roadguard/model/roadguard-yolo11s-single-v1.pt` and arrive with normal clone/pull. The backend loads them there by default. Install backend and vision dependencies from the model integration guide in a new environment, then start; no separate download or model-path change is needed. See the [backend model directory](roadguard/model/README.md).

A maintains one FastAPI application, configuration, SQLite connection layer, errors and router registration. Implemented features include health checks, stateless demo previews, persisted image inspections/review/tasks and opt-in trusted local real vision. Real primary confidence >= 0.60 creates one task; lower confidence requires review; business rules and tasks remain demo assumptions. B's crew availability and Greedy/GA route plans are implemented on a labelled simulated travel matrix by default, with an opt-in Google Routes travel matrix (B-5, see the [routing guide](roadguard/routing/README.md)); the database schema is now v5, retaining crews, saved plans, accounts, sessions and inspection ownership, and adding assistant change requests and audit records. The authenticated [React frontend](../frontend/README.md) and fixed-crew completion are implemented; the assistant provides local knowledge retrieval, opt-in GPT evidence selection and confirmed crew-change orchestration; real GPT acceptance remains outstanding. Public formats are in [API contract](../../Miscellaneous/API_CONTRACT.md); inspection responses now use a-workflow-v5, while a-task-query-v1 stays unchanged. See [real vision setup and API](../../Miscellaneous/REAL_VISION_API.md) for checkpoint provenance, optional dependencies, failure behavior and compatibility.

Successful upload returns only `inspection_id`, `status`, `detection`, `task_id`. Read details with `GET /api/v1/inspections/{id}`. See the [database viewing guide](../../Miscellaneous/DATABASE_VIEWING.md) for database location, PyCharm access and read-only SQL.

## Environment and startup

Use Python 3.12 for the full application with real vision; pinned NumPy 2.5.2 requires Python >=3.12. Recorded local acceptance used Python 3.12.14. Base CI uses Python 3.11 without the optional vision dependencies. `requirements.txt` pins FastAPI, Pydantic, Uvicorn, Pillow for image decoding and python-multipart for multipart parsing. `requirements-ci.txt` includes these plus HTTPX and pytest. SQLite uses the standard library. Reinstall requirements in existing environments to obtain new packages.

Run these commands from the repository root; create and activate a Python 3.12 environment on first use. If an existing `.venv` uses another Python version, create a separate environment with 3.12 and use that environment consistently; do not recreate an environment in use. Provision accounts following the [complete installation guide](../../ProjectReport/INSTALLATION_AND_USER_GUIDE.md). Fresh-machine installation has not been independently validated:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r SystemCode/backend/requirements-ci.txt
python -m pip install -r SystemCode/model/requirements-vision.txt
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

Local health URL: `http://127.0.0.1:8000/api/v1/health`; interactive docs `/docs`; OpenAPI `/openapi.json`. Routes also cover inspection upload/query/images/review and task query/mutation. `roadguard.main.create_app(settings=None)` creates an isolated application without initializing the database. Lifespan validates configuration, demo rules and frozen geography before migrations. Configuration, directory-permission or schema errors fail startup without rebuilding existing business data. Business APIs authenticate three account roles and sessions; use the [account roles guide](../../Miscellaneous/ACCOUNT_ROLES.md) to provision inspectors, fixed-crew accounts and central dispatchers. Deployment remains local development, not public hosting.

Health response:

```json
{"status":"ok","database":"ok","api_version":"v1","input_revision":0}
```

This means only that the application and SQLite foundation are readable, not that the model, road-travel API, GA or assistant is ready. Unreadable databases, missing tables or incompatible versions after startup return HTTP 503.

## Run Step 5

In `/docs`, call `GET /api/v1/demo/scenarios`, then send `{"scenario_id":"high_confidence"}` to `POST /api/v1/demo/assessments`. The default yields a P2, 120-minute demo candidate; `low_confidence` yields pending_review and `no_detection` yields no candidate. See the [demo detection/rules guide](../../Miscellaneous/DEMO_DETECTION_AND_RULES.md) for seven scenarios, threshold boundaries and eight-class demo mappings. These endpoints accept no images, create no database records and do not update input_revision.

## Step 7: task and knowledge integration

`GET /api/v1/tasks/snapshot` returns all active Tasks and input_revision from one transaction, with optional expected_revision. `/tasks` retains paginated page/TaskRecord-history uses. B's internal entry is `TaskQueryService(database).snapshot(expected_revision=None, *, connection=None)`, available as `request.app.state.task_query_service`. Supplying an existing transaction connection from the same database permits a shared snapshot with B's crew queries; the service does not end the caller's transaction.

See the [B/C handoff](../../Miscellaneous/BC_HANDOFF.md) for contracts, revision checks during calculation/save, fixed 10/15/20-task sets and actual HTTP consumption examples. The current [a-knowledge-v10 corpus](knowledge/README.md) has eleven citable documents and 30 synthetic assistant acceptance specifications, including GA/Greedy, saved-plan explanations, account permissions, operations and historical evaluation evidence. Sources are checked against repository facts, not engineering-expert approval. The original Step 7 handoff introduced no dependencies or migrations; later routing/frontend integration is implemented, while retrieval/generation remains pending.

Current course-simulation rules are `demo-rules-v2`: P3/P2/P1 = 60/120/240 minutes. New inspections use startup configuration; older records retain frozen rules without automatic recalculation. See the [business baseline](../../Miscellaneous/BUSINESS_RULES_BASELINE.md) for definitions/version effects and [integration checklist](../../Miscellaneous/INTEGRATION_ACCEPTANCE_CHECKLIST.md) for this stage's checks. Frontend and planning integration is recorded in the [18 October acceptance](../../Miscellaneous/INTEGRATION_ACCEPTANCE_20261018.md); the assistant remains outside that acceptance.

## Configuration entry points

The original demo upload/review/task behavior is documented in the [workflow guide](../../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md). Uploads explicitly select demo mode with a named scenario, or real mode without a scenario. Real mode requires the optional locally configured detector; the selected primary result creates one task at the configured confidence threshold (default 0.60), otherwise waits for review. All inspection HTTP responses contain at most one box, with raw evidence retained internally. See [every response field](../../Miscellaneous/INSPECTION_RESPONSE_FIELDS.md). Accepted tasks remain persisted demo business objects. Road type is user-declared. The [Step 8 guide](../../Miscellaneous/REAL_VISION_API.md) describes this extension.

Defaults read `SystemCode/config/project.example.json` and `SystemCode/config/demo_rules.example.json`, with database `SystemCode/backend/data/roadguard.sqlite3`. Local databases are not committed. Supported environment variables:

| Variable | Purpose |
| --- | --- |
| `ROADGUARD_CONFIG_PATH` | Local UTF-8 JSON project configuration |
| `ROADGUARD_DB_PATH` | Persistent SQLite file |
| `ROADGUARD_DEMO_RULES_PATH` | Override demo-rule path; validated at startup, requiring restart and rule-version update after changes |
| `ROADGUARD_UPLOAD_PATH` | Image directory, default uploads beside the database; preserve/back up with the database |
| `ROADGUARD_VISION_MANIFEST_PATH` | Defaults to `SystemCode/model/releases/roadguard-single-v1.json`, which loads the Git-bundled `SystemCode/backend/roadguard/model/roadguard-yolo11s-single-v1.pt`. Set `disabled` to turn off real inference. A local manifest path overrides the default. Relative paths resolve from the repository root. Model loading is lazy; restart after repairing a failed load. |
| `ROADGUARD_TRAVEL_MATRIX_PROVIDER` | B's travel matrix: `simulated` (default, routing configuration) or `google_routes`. Invalid values fail startup; Google failures return 503 on recalculation without simulated fallback. |
| `ROADGUARD_GOOGLE_MAPS_API_KEY` | Server-side Routes API key used only with `google_routes`; set locally, never in configuration, logs, responses or frontend. |

Default and overridden relative paths resolve from repository root regardless of working directory; absolute paths are local user overrides only. Empty paths, unreadable files, invalid JSON, duplicate keys, non-finite numbers and malformed base objects fail explicitly. `Settings` and nested project dictionaries/lists are immutable. Base validation requires nonempty `project_name` plus `scenario` and `planning` objects; it does not guess unfrozen thresholds, service durations, shifts or return policy. The example's four crews, area and `return_to_depot: null` retain their meaning. Future model/external API credentials belong to module-defined environment variables, never example files or responses.

## Shared SQLite and planning input revision

`roadguard.database.Database` is shared across modules. Each operation obtains and closes its own connection with foreign keys enabled and a 5000-ms busy timeout. `connect()` supplies a read-only consistent transaction snapshot. `transaction(expected_revision=None)` serializes writes with `BEGIN IMMEDIATE`, commits on success and rolls back on exceptions. Do not manually commit, roll back or close inside these contexts.

`initialize()` is the sole migration entry. Base schema v1 migrates in place to v2, preserving input_revision and adding inspections, tasks, operation_keys and indexes; new databases start at revision=0. Restarting v2 validates existing structures in a read-only transaction so long-running viewer queries do not block unnecessary write commits; creation/migration still revalidates and commits in a write transaction. Unknown versions or missing business tables fail startup without clearing/rebuilding records. B/C provide incremental table definitions for A to integrate through this same entry.

For `sqlite3.OperationalError: database is locked`, follow [database-lock troubleshooting](../../Miscellaneous/DATABASE_VIEWING.md#handling-database-is-locked), finish pending viewer transactions and disconnect. Read-only startup validation does not guarantee subsequent writes: exclusive locks block reads too, while migration, upload persistence and task mutation require write locks.

Shared A/B functions are `read_revision(connection)`, `assert_revision(connection, expected_revision)` and `increment_revision(connection, expected_revision=None)`. Input mutation and revision increment must occur in **the same domain transaction**, once per actual input change. Do not use independent counters or a second later connection to update versions. For example, B's crew-status service should use:

```python
from roadguard.database import increment_revision, read_revision

with database.connect() as connection:
    input_revision = read_revision(connection)
    # Read implemented task/crew service data from the same snapshot.

with database.transaction(expected_revision=input_revision) as connection:
    # Call the owning domain's write methods here; not implemented in this example.
    new_revision = increment_revision(connection, expected_revision=input_revision)
```

This illustrates transaction boundaries, not a crew implementation. `expected_revision` is checked when the write transaction starts; stale versions raise `StaleRevisionError` (HTTP 409) before caller mutations. Incrementing does not commit; domain failure rolls back revisions too. Plan persistence must also check its input revision inside its write transaction. Saving a plan does not change planning input and must not increment input_revision. B's implemented planning services own explicit recalculation, plan storage and stale-state reporting.

## Errors and module integration

Responses use `{"code":"...","message":"...","details":null}`; details may be a JSON object or list. Implemented errors:

| HTTP status | code | Meaning |
| --- | --- | --- |
| 404 | `not_found` | Resource/path missing |
| 405 | `method_not_allowed` | Unsupported HTTP method; retain Allow header |
| 422 | `validation_error` | Request validation failed; details contains only error_count |
| 409 | `stale_input_revision` | Stale input revision; details includes expected_revision/current_revision |
| 503 | `database_unavailable` | Health cannot read a valid base database |
| 500 | `internal_error` | Unhandled error with a fixed safe message |

Other HTTPException responses use `http_error` and fixed messages. Errors never copy URLs, query parameters, validation inputs, database paths, exception messages or tracebacks. Future modules using `AppError(code, message, status_code, details)` must supply fixed public messages and safe structured details, never exceptions or credentials. Unhandled-exception logs record only exception type.

A registers B/C `APIRouter` instances centrally under `/api/v1` in `roadguard.api.create_api_router()`. Database and settings are available through `request.app.state.database` and `request.app.state.settings`. Domain services own business semantics and tables; the future assistant must execute confirmed changes through them. Empty business endpoints are not mounted, and API failures never fabricate simulated success.

## Validation

Run the same entry as CI from repository root:

```powershell
python -m pytest SystemCode/tests -q
```

Foundation tests cover configuration, actual responses/OpenAPI, migrations, persistence, rollback and concurrency. vision/rules/demo API tests verify fixed scenarios, demo mappings and previews without database writes. Step 6 added geography/images/workflow/API tests for images/coordinates, review, task state, idempotency, resource versions and historical rule snapshots. Tests use temporary databases/images; they do not establish real-model, road-network, four-crew-planning or whole-system completion.

## Account endpoints (2026-10-18)

`POST /api/v1/auth/login` sets a session cookie; `GET /api/v1/auth/session` returns the current account. Writes require `X-CSRF-Token`. Crews use `GET /api/v1/crew/workspace` for their own snapshots; anonymous business access is denied. Schema v4 migrates incrementally while preserving data. See [account roles](../../Miscellaneous/ACCOUNT_ROLES.md) for provisioning, Swagger tests and deployment settings.

## Assistant retrieval, evidence answers and crew changes (2026-10-21)

The dispatcher-only assistant uses the existing session, role and CSRF checks:

- `POST /api/v1/assistant/knowledge/search` returns versioned static passages, stable citations and source integrity metadata; it does not generate answers or read business plans. Rule-version mismatch returns empty hits; inconsistent knowledge returns `503 knowledge_unavailable`.
- `GET /api/v1/assistant/status` exposes non-secret configuration status. `POST /api/v1/assistant/query` accepts question, scope and optional plan_id/rule_version. Plan questions require an explicit saved plan loaded through B's query service. `c-assistant-query-v1` returns verified evidence extracts and provenance without business changes. Real GPT connectivity and semantic quality remain unverified.
- `/api/v1/assistant/change-requests` provides preview/history and per-request confirm/cancel/replan operations under `c-assistant-change-v1`. Preview does not change planning input. Confirmation and recalculation are separate explicit actions; history supports uncertain-outcome recovery. This flow does not call GPT.

Schema v5 adds persistent assistant change requests and audit records while retaining v4 accounts, sessions, ownership, crews and plans. No new dependency or model weight is required. The assistant guide defines limits, concurrency, idempotency, failure handling and server-only provider configuration.

See [assistant contracts and configuration](roadguard/assistant/README.md).

## Chroma retrieval update (2026-10-21)

The dispatcher search endpoint now returns `c-knowledge-search-v2` with `retrieval_method=chroma-e5-cosine-v1`. Static sources use local E5 embeddings and a versioned persistent Chroma index. Scores are cosine similarity; `matched_terms` is an empty compatibility field. Model/index failures are explicit 503 responses, and oversized encoder inputs return 422. The answer and crew-change contracts are unchanged. Follow the [setup and maintenance guide](roadguard/assistant/VECTOR_RETRIEVAL.md) before querying; runtime data stays outside Git.
