# Installation and user guide

This guide covers the implemented local inspection-to-completion prototype and matches Appendix A of the final report. Local acceptance used Windows, Python 3.12.14 and Node 22.23.3. Independent installation on a clean machine has not been validated.

## Environment and dependencies

Use **Python 3.12** for the full application: the pinned `numpy==2.5.2` requires Python >=3.12. Base CI uses Python 3.11 without installing the optional vision dependency set, so its success is not evidence that vision runs on 3.11. Use Node 22.x >=22.12 and npm >=10.

Clone the private repository with authorised access. The approved YOLO checkpoint is included in `SystemCode/backend/roadguard/model/`; Dataset is not required for inference. From the repository root, create a new environment on first use:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r SystemCode/backend/requirements-ci.txt
.\.venv\Scripts\python.exe -m pip install -r SystemCode/model/requirements-vision.txt
```

If an existing `.venv` uses another Python version, create a separate Python 3.12 environment and substitute its path in all commands. Do not recreate an environment while it is in use. CPU inference is supported by the recorded local acceptance; GPU training has separate CUDA requirements.

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

The frontend map shows schematic stop order, not turn-by-turn navigation. The assistant page remains a placeholder without GPT/RAG answers or change execution. See the [frontend guide](../SystemCode/frontend/README.md).

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
| Google provider error | Check server credentials/service access; errors do not silently become simulation |

## Optional Google travel estimates

Set these variables in the backend terminal, then restart and explicitly recalculate:

```powershell
$env:ROADGUARD_TRAVEL_MATRIX_PROVIDER = 'google_routes'
$env:ROADGUARD_GOOGLE_MAPS_API_KEY = '<your private key>'
```

Usage may incur charges. Keep the key private and out of frontend source. The current provider uses traffic-unaware estimates; the map remains schematic. Old plans retain their original source. Recorded browser acceptance used simulation, not a new real-Google call. See the [routing guide](../SystemCode/backend/roadguard/routing/README.md).
