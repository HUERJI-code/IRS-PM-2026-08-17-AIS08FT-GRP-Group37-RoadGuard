# Installation and user guide

This guide covers local installation, the inspection-to-completion workflow and dispatcher assistant. The final report reproduces this complete guide in Appendix A. Local acceptance used Windows, Python 3.12.14 and Node 22.23.3. Independent installation on a clean machine has not been validated.

## Environment and dependencies

Use **Python 3.12** for the full application: the pinned `numpy==2.5.2` requires Python >=3.12. Base CI uses Python 3.11 without installing the optional vision dependency set, so its success is not evidence that vision runs on 3.11. Use Node 22.x >=22.12 and npm >=10.

Clone the private repository with authorised access. The approved YOLO checkpoint is included in `SystemCode/backend/roadguard/model/`; Dataset is not required for inference. From the repository root, create a new environment on first use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r SystemCode/backend/requirements-ci.txt
.\.venv\Scripts\python.exe -m pip install -r SystemCode/model/requirements-vision.txt
```

If an existing `.venv` uses another Python version, create a separate Python 3.12 environment and substitute its path in all commands. Do not recreate an environment while it is in use. CPU inference is supported by the recorded local acceptance; GPU training has separate CUDA requirements.

## Local retrieval and optional GPT configuration

Install the full backend requirements and prepare the reviewed local knowledge index before using evidence questions. Run these commands from the repository root after creating the Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r SystemCode/backend/requirements.txt
$env:PYTHONPATH = 'SystemCode/backend'
.\.venv\Scripts\python.exe -m roadguard.assistant.index_knowledge --download-model
```

First setup downloads approximately 487 MB of pinned multilingual-e5-small model/tokenizer files and verifies their hashes. The encoder uses ONNX Runtime on CPU; it does not call an embedding API or change the YOLO model. Subsequent setup reuses verified files. After pulling a reviewed knowledge update, rebuild the current index with `.\.venv\Scripts\python.exe -m roadguard.assistant.index_knowledge` and restart the backend. HTTP requests never download models or rebuild indexes. The current package is `a-knowledge-v17`; Chroma collections are versioned against the manifest, encoder and chunking policy.

The default Chroma path is `SystemCode/backend/data/rag/chroma/`; embedding files are under `SystemCode/backend/data/rag/models/multilingual-e5-small/`. Both are ignored local runtime storage. Server-side overrides are `ROADGUARD_CHROMA_PATH` and `ROADGUARD_EMBEDDING_PATH`. Dataset, uploads, account records and business databases are not indexed. Retrieval uses cosine similarity, whose score is not answer correctness. See the [vector retrieval guide](../SystemCode/backend/roadguard/assistant/VECTOR_RETRIEVAL.md).

GPT generation is disabled by default. To enable it, set these variables privately in the backend terminal before startup:

```powershell
$env:ROADGUARD_ASSISTANT_ENABLED = 'true'
$env:ROADGUARD_ASSISTANT_MODEL = 'gpt-4.1-mini'
$privateKey = Read-Host 'OpenAI API key' -AsSecureString
$env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $privateKey).Password
Remove-Variable privateKey
```

`gpt-4.1-mini` is the model used in the recorded targeted acceptance; select only a model available to your account. The enabled flag accepts exactly lowercase `true` or `false`; uppercase `True` is invalid. Restart the backend after changing environment settings. Never place the key in frontend code, Git or the report. The status endpoint reports non-secret configuration and usage, not credential validity. Optional limits are `ROADGUARD_ASSISTANT_MAX_OUTPUT_TOKENS` (default 1200, range 256–2000) and `ROADGUARD_ASSISTANT_MAX_CALLS` (default 20 per process, range 1–200). Attempted calls, including failures, consume the local budget; it resets on restart and is not an account-wide spending cap. Real provider requests may incur charges. There are no automatic retries or model fallbacks.

## Accounts and data

No default accounts or shared passwords are shipped. Provision accounts in the same database used by the server; each command privately prompts for a 12–256-character password:

```powershell
$env:PYTHONPATH = 'SystemCode/backend'
.\.venv\Scripts\python.exe -m roadguard.auth.manage create inspector --role inspector
.\.venv\Scripts\python.exe -m roadguard.auth.manage create dispatcher --role dispatcher
.\.venv\Scripts\python.exe -m roadguard.auth.manage create crew02 --role crew --crew crew-02
```

Provision distinct usernames for crew-01, crew-03 and crew-04 when needed. Crew identity is fixed by the account. Accounts and passwords are local database records, not shared through Git. The default database is `SystemCode/backend/data/roadguard.sqlite3`; back it up with its adjacent `uploads` directory. If `ROADGUARD_DB_PATH` is customised, use the same value when provisioning accounts and starting the server. See [account roles](../Miscellaneous/ACCOUNT_ROLES.md).

## Start the application

Backend, from the repository root:

```powershell
$env:ROADGUARD_TRAVEL_MATRIX_PROVIDER = 'simulated'
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```powershell
cd SystemCode/frontend
npm ci
$env:ROADGUARD_API_TARGET = 'http://127.0.0.1:8000'
npm run dev
```

Open `http://127.0.0.1:5173` and sign in. API documentation is at `http://127.0.0.1:8000/docs`; the public health endpoint is `/api/v1/health`. Health checks application/database access only, and the model loads lazily on real inference. Stop the appropriate terminal with Ctrl+C. Do not start duplicate servers on occupied ports.

## User workflow

1. Sign in as an inspector. Upload a JPEG or PNG within 8 MiB and 20 megapixels, choose real inference or an explicit synthetic scenario, enter Jurong coordinates and declare road type. Coordinates such as 1.3405, 103.706 are synthetic unless verified as the photo's location.
2. Inspect the result. Upload returns `inspection_id`, `status`, one `detection` or null, and `task_id`. Real primary raw confidence >=0.60 creates one task; lower confidence requires review, and no detection creates no task. Raw evidence and frozen rules remain available in inspection details.
3. Sign in as the dispatcher. Confirm, correct or reject pending inspections; corrections use stored rules. Accepted tasks contain the demonstration priority and service duration. Completed/cancelled records retain history and leave the active planning snapshot.
4. Check crew availability and explicitly recalculate. Both planners use the same snapshot and matrix. Inspect unassigned reasons and the same-round comparison. Changes make existing plans stale; they do not trigger automatic recalculation.
5. Sign in as the crew assigned by the latest saved GA plan. View and complete that crew's tasks; the server checks current assignment and task version. Completion changes planning inputs, and dispatch must explicitly replan.

The frontend map shows schematic stop order, not turn-by-turn navigation. See the [frontend guide](../SystemCode/frontend/README.md).

## Dispatcher evidence questions

Sign in as a dispatcher and open Route assistant. Ask about a supported repair rule or project operation, or select an explicit saved plan for route questions. Saved-plan answers use authorized persisted facts rather than browser-supplied totals. English and bounded Chinese question aliases are supported; generated answers and the interface are English.

Read the answer first. Sources are closed by default; expand View sources to inspect exact quotations, citation IDs, package/version hashes and saved-plan provenance. The query-v3 `grounded_summary` mode uses local Chroma/E5 retrieval and one optional GPT call. GPT chooses server-owned evidence IDs; the server restores exact quotations and required context. Canonical repair answers are rendered from the matching rule rows, preserving demonstration qualifiers. Number, priority, identifier, label, source and plan checks reject unsupported output. These bounded checks do not establish universal semantic correctness.

A standalone question such as “What model are you?” returns the configured model name using `server_configuration`, without GPT, retrieval or saved-plan reads. It remains usable when generation is disabled or the key is missing. It identifies configuration, not proof of provider execution or the separate YOLO detector. Clearly unrelated questions return `scope_guidance` with RoadGuard examples. These direct modes have no citations or knowledge-package metadata and consume no model-call budget. Ambiguous or mixed domain questions retain the evidence flow; insufficient evidence and validation failures remain explicit.

Queries do not change tasks, crew availability or routes. A model answer never authorizes a business action.

## Dispatcher route previews and confirmed adjustments

Open Crew adjustments in Route assistant and load a saved plan ID or the latest GA plan. Four crew cards show stop order, travel, service, required return travel, total work, remaining shift and persistent assignment badges. Use a current plan for changes. Crew availability changes remain a separate preview and confirmation workflow.

To move a task, select an assigned active task and a different available crew, then preview. Inspect before/after routes and acknowledge the preview before confirming. The server retains all other assigned work and checks travel plus service plus configured depot return against the shift limit (480 minutes in the routing demo). Unknown travel, infeasible work, stale input/configuration or expired previews are rejected without mutation. A rejected move never silently drops another task.

Confirmation stores a durable task-to-crew constraint; it does not save a new route automatically. Choose Recalculate saved task change and reload the latest GA plan. Both Greedy and GA retain the constraint after restart and when new tasks are added. Stop order may change. Unavailable or infeasible constrained tasks are reported as unassigned instead of silently changing crews. The shift and return policies remain configurable demonstration assumptions.

To cancel work, choose Cancel active task, preview and explicitly confirm. Assigned and unassigned active tasks can be cancelled. Cancellation retains task/history records and removes the task from active planning; explicitly recalculate to replace stale routes. Completed and cancelled tasks cannot be reopened. Discard task preview closes only an unconfirmed proposal and does not cancel a task. Use recent records or the change ID to recover after interruption; refresh before retrying a version conflict. Confirm/replan retries are bounded and idempotent.

Reassignment immediately removes the previous crew's task/inspection read and completion access. The target crew waits for an explicit saved GA recalculation. An affected old route is omitted with a stale/recalculation explanation. Crew and inspector accounts cannot perform dispatcher adjustment operations. These checks apply in the backend as well as the interface.

## API testing and troubleshooting

In Swagger, call `POST /api/v1/auth/login` with a provisioned account. Keep the same host name for session cookies, and send the returned `csrf_token` as `X-CSRF-Token` for authenticated modifying requests. Upload uses multipart image and metadata, with a new `Idempotency-Key` for each new submission. Retry a lost response with identical content and the same key.

| Issue | Action |
| --- | --- |
| Dependency installation rejects NumPy | Check the environment interpreter is Python 3.12; base CI's 3.11 does not include vision |
| Connection refused | Start the backend and match the frontend proxy target |
| 401/403 | Check sign-in, account role, session host and CSRF token |
| Database locked | End outstanding viewer transactions; do not delete the database |
| Real inference unavailable | Install vision requirements, verify the bundled weight/manifest and restart after a failed load |
| Stale plan or 409 | Refresh current state and explicitly replan or retry with the current record version |
| Unassigned tasks | Read the reasons, including unavailable crews or shift limits |
| Embedding model unavailable or index missing/stale | Install full backend requirements, verify configured paths, run the explicit index command and restart; HTTP requests do not repair indexes |
| Invalid assistant configuration | Use lowercase true/false, a valid model name and documented limit ranges, then restart |
| GPT unavailable, quota or provider error | Check private server configuration, account access and local attempted-call budget; model identity remains available; do not repeatedly retry unknown outcomes |
| Insufficient evidence or rejected answer | Narrow the question or select a current saved plan; inspect the explicit error, without bypassing citation validation |
| Task preview expired or 409 | Refresh task/plan/configuration and create a new preview before confirmation |
| Move exceeds shift or travel is unknown | Inspect travel/service/return totals and availability; choose a feasible crew; other tasks are retained |
| Constrained task unassigned | Inspect the locked crew and reason; later recalculation preserves the constraint rather than silently transferring work |
| Crew access lost after reassignment | Dispatcher explicitly recalculates; the target crew then refreshes its latest saved GA route |
| Google provider error | Check server credentials/service access; errors do not silently become simulation |

## Optional Google travel estimates

Set these variables in the backend terminal, then restart and explicitly recalculate:

```powershell
$env:ROADGUARD_TRAVEL_MATRIX_PROVIDER = 'google_routes'
$env:ROADGUARD_GOOGLE_MAPS_API_KEY = '<your private key>'
```

Usage may incur charges. Keep the key private and out of frontend source. The current provider uses traffic-unaware estimates; the map remains schematic. Old plans retain their original source. Recorded browser acceptance used simulation, not a new real-Google call. See the [routing guide](../SystemCode/backend/roadguard/routing/README.md).
