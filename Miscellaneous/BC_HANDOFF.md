# Step 7: A's handoff to B/C

Date: 2026-10-12; current-status update: 2026-10-20; owner: A. The original handoff delivered consistent active-task queries, fixed inputs, citable project knowledge and actual HTTP examples. Planning, crew APIs and authenticated pages have since been integrated; retrieval/generated answers and assistant confirmation remain unimplemented. Inspections support explicit demo or real models; task parameters remain course-simulation rules. Historical acceptance numbers below describe their dated runs.

a-workflow-v5 caller changes: uploads return only inspection_id, status, detection, task_id. C displays detection, then GET /inspections/{id} before review for detection ID/record version. Query automatic tasks with GET /tasks/{task_id}, and planning revision through /tasks/snapshot. The integration script uses this sequence.

Current `demo-rules-v2` sets P3/P2/P1=60/120/240 minutes; fixtures were regenerated as `planning-synthetic-v2`. B reads saved durations rather than recalculating v1 as v2. That round supplied knowledge v6; the current ingestion target is [a-knowledge-v10](../SystemCode/backend/knowledge/README.md), with eleven documents and 30 synthetic acceptance specifications. See [baseline](BUSINESS_RULES_BASELINE.md)/[checklist](INTEGRATION_ACCEPTANCE_CHECKLIST.md). B/C integration was outside the original round and is documented separately in the later acceptance record.

## 1. Deliverables and boundaries

| Consumer | Deliverable | Entry |
| --- | --- | --- |
| B | Complete unpaginated snapshot/service | `roadguard.tasks.TaskQueryService`; `GET /api/v1/tasks/snapshot` |
| B/C | `a-task-query-v1` models | [schemas/task_query.py](../SystemCode/backend/roadguard/schemas/task_query.py) |
| B | 10/15/20 tasks, empty queue/edge inputs | [Fixed inputs](../SystemCode/contracts/planning/README.md) |
| C | Versioned sources/stable citation IDs | [Knowledge](../SystemCode/backend/knowledge/README.md) |
| C | Inspection/review/task requests/status/errors | [Step 6](INSPECTION_REVIEW_TASK_WORKFLOW.md), [API](API_CONTRACT.md), running `/docs` |
| B/C | Actual API calls/exported responses | [handoff_demo.py](../SystemCode/examples/handoff_demo.py) |

This freezes A's task output, not B's complete `PlanningInput`, Crew, RoutePlan, matrix, shifts or objective. C still owns retrieval/generation; the knowledge package calls no GPT and builds no vector index.

## 2. B: all active tasks at one revision

```http
GET /api/v1/tasks/snapshot
GET /api/v1/tasks/snapshot?expected_revision=12
```

Actual empty-database structure:

```json
{
  "contract_version": "a-task-query-v1",
  "source": "persisted_workflow",
  "input_revision": 0,
  "tasks": [],
  "total": 0,
  "is_demo": true
}
```

| Field/behavior | Agreement |
| --- | --- |
| tasks | Every active Task with exact original `a-dto-v1` fields, without TaskRecord history/record_version extras |
| total | Equals tasks length; no 50/100 default truncation |
| Order | created_at/task_id ascending; stable nodes, not recommended visit order |
| input_revision | Same read transaction as tasks; neither task count nor record revision |
| expected_revision | Optional nonnegative integer; mismatch is 409 stale_input_revision, never mixed data |
| source | Live persisted_workflow versus fixed synthetic_fixture; fixtures cannot impersonate live revisions |
| is_demo | Explicit demonstration tasks, including real detection acceptance/review with demo business rules |
| Empty | 200, tasks=[], total=0, valid revision; DB failure is 503, not empty success |

Queries never write/create/increment. Completed/cancelled tasks leave snapshots but remain in details/history lists. No-detection/pending/rejected inspections never form active tasks. service_minutes=null is unknown, not zero; due_at=null is no known deadline, not invented lateness. B reads saved label/priority/duration rather than remapping labels.

UI pagination remains `GET /tasks?status=...&limit=...&offset=...` returning historical TaskRecord. Do not combine pages from different revisions for planning. Each snapshot item parses directly as the strict Task DTO without extra audit fields.

### Shared backend connection

```python
TaskQueryService(database).snapshot(expected_revision=None, *, connection=None)
```

Without connection, the service opens/closes one read transaction. The implemented PlanningService reads tasks and crews together using one connection:

```python
from roadguard.tasks import TaskQueryService

query = TaskQueryService(database)
with database.connect() as connection:
    snapshot = query.snapshot(connection=connection)
    # CrewService.read_planning_crews(connection) reads crews in this transaction.
    # Do not invoke a crew query that opens another connection in this context.

# Compute matrix/Greedy/GA after exiting the read transaction.
# When B saves results:
# with database.transaction(expected_revision=snapshot.input_revision) as connection:
#     Save B's plan here; saving a plan does not increment input revision.
```

The snippet illustrates the transaction boundary; the executable integration is [PlanningService](../SystemCode/backend/roadguard/routing/service.py). Supplied connections must belong to the same file database and already be in a transaction. The caller owns commit/rollback/close; TaskQueryService does not.

Snapshots are consistent at read time, not locks on future state. Tasks/crews can change during computation. Recheck input_revision in the saving write transaction, discarding/recalculating stale results under B's policy rather than overwriting current plans. A pre-computation check alone is insufficient.

HTTP snapshots include only tasks and do not guarantee that crews read through another request share their revision. B combines inputs internally with the shared connection above. Saved plans are marked stale on read when input_revision differs. Task/crew changes do not automatically recalculate: planning_input_changed signals input changes, and explicit recalculation saves both plans only after a second revision check.

## 3. B: fixed inputs

See [planning/README.md](../SystemCode/contracts/planning/README.md) for files/reproducible generator. 10/15/20 tasks are subsets of one sequence, without matrices/results/training images. Coordinates pass frozen-polygon checks but are synthetic and not verified on eligible roads; they are neither field tasks nor road-verified experiments.

Configuration retains four crews/NUS-ISS building reference. Vehicle access and road eligibility remain unverified. The routing demo explicitly selects return_to_depot=true, a 480-minute shift and b-objective-v1 weights; shared operational approval and task deadlines remain unresolved. Optional Google estimates do not verify permission.

Fixture revisions apply only within fixtures, never as live database revisions. No automatic import or fallback success on query failure. Fair GA/Greedy comparisons also require identical task snapshot, crews, node order, matrix and constraints, with versions/seeds recorded.

## 4. C: retrieval and UI integration

Knowledge retains stable document/passage IDs, sources/hashes, versions, responsibility and consistency checks. Checks are coding-agent reviews against repository facts, not engineering-expert approval. Distinguish confirmed facts, demo assumptions and pending decisions.

Retain citation ID/version/classification/original source in retrieved passages and answers. `demo-rules-v2` cannot automatically explain tasks frozen under another version; check saved rule_version/decision/audit first and state insufficient version evidence.

Specific routes, assignments, travel times and GA/Greedy metrics must come from authorized saved plans, not static knowledge. Comparable algorithm percentages require same-recalculation evidence and matching inputs; equivalent-work time comparisons also require matching assigned task IDs. Availability changes require user confirmation/B's service; CrewPatch checks expected_version and does not automatically recalculate. The planned assistant orchestration must validate preview state, then call planning with the returned input_revision. Knowledge/model answers cannot write tables. Knowledge QA cases specify future behavior and are not executed GPT/RAG results. See the [RAG integration contract](../SystemCode/backend/knowledge/11_assistant_integration.md) for source lifecycle, permissions and confirmation boundaries.

Frontend notes:

- Explicit demo-case selection; show is_demo, raw confidence, decision_trace, rule_version and user-declared road type.
- Distinguish no detection, pending, accepted, rejected. Review only pending_review; confirm/correct requires selected detection.
- Retry a logical action with its key; a new action gets a new key. After reload/conflict resolution, use a new request_id.
- Fill expected_version from record_version. Refresh on 409 stale_record_version without overwrite; idempotency_conflict means reused key/different content.
- Retry can return current state, not initial state. replayed=true must not announce another new task.
- annotated_image_url is currently null; draw original-pixel boxes over saved normalized images using response dimensions.
- Refresh tasks after changes; planning_input_changed=true does not mean a new route exists.

## 5. Actual HTTP handoff example

Install requirements-ci.txt per the [backend guide](../SystemCode/backend/README.md). Run from root in PowerShell with an isolated development database retaining generated inspections/audits:

```powershell
$env:ROADGUARD_DB_PATH = 'SystemCode/backend/data/handoff-demo.sqlite3'
$env:ROADGUARD_UPLOAD_PATH = 'SystemCode/backend/data/handoff-demo-images'
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

Activate the same environment in another terminal at root:

```powershell
python SystemCode/examples/handoff_demo.py --confirm-demo-writes
```

The script generates a synthetic PNG through real HTTP and checks automatic acceptance, low-confidence correction, repeated review, no detection, dismissal, completion/cancellation, consistent snapshots and stale conflicts. Each run adds four inspections and two eventually completed/cancelled tasks; without concurrent writers, the active set returns to its previous state and input_revision increases 4. Do not run against a database in concurrent use.

Use `--base-url http://127.0.0.1:8001` or `--output <new-file.json-in-existing-directory>` to export actual responses for C or clearly labeled frontend fixtures. Output cannot overwrite existing files; do not commit local run records. Responses are checked and failures immediately reported without fabricated success; records already created before failure remain queryable.

Without --confirm-demo-writes, the script refuses to run to prevent accidental writes while reading documentation. Exports omit server images; image_url works only while that server retains the record/image.

## 6. Acceptance and next steps

```powershell
python -m pytest SystemCode/tests -q
```

Tests cover complete queries above 100 tasks, original-field projection, unknowns, terminal filtering, conflicts/concurrency, caller connection lifecycle, corrupt data, reproducible fixtures, knowledge-source consistency and HTTP example. No real training, Google travel, planning, GPT or frontend demo was executed.

See [Step 8](STEP8_VISION_ACCEPTANCE.md) for its dated data/model acceptance. C must use a-workflow-v5 (at most one box, nullable auto_acceptance, primary ≥0.60 auto-task) and the current [a-knowledge-v10](../SystemCode/backend/knowledge/README.md); installation is in the [current guide](../ProjectReport/INSTALLATION_AND_USER_GUIDE.md). Display real detection/demo business flags separately. Existing A/B/C modules were integrated on 2026-10-18; see the [record](INTEGRATION_ACCEPTANCE_20261018.md). The v10 corpus now covers implemented GA/Greedy, saved plans, accounts and historical evaluations. Verify manifest digests before ingestion; the assistant remains unimplemented.
