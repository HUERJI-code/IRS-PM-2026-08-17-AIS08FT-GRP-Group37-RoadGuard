# Task adjustment and English interface acceptance

Date: 2026-10-21. Delivery: local working tree only; no commit, push or PR.

## Implemented workflow

Open Route assistant, expand Crew adjustments, and load an explicit plan ID or the
latest GA plan. Four crew cards show ordered tasks, travel, service, return travel,
total work, remaining shift and persistent assignment badges. On a current plan,
select a task and a different available crew, then preview and explicitly confirm.
The server retains other assigned tasks and checks travel + service + required
return against the configured shift (currently 480 minutes). Rejected changes do
not mutate business records. Click Recalculate saved task change and reload the
latest GA plan to inspect the saved result.

Confirmed reassignment persists across new tasks and later Greedy/GA recalculation.
Stop order may change. Unavailable or infeasible locked assignments become explicitly
unassigned rather than silently moved. Cancel active task supports assigned and
unassigned active tasks and preserves task/history records. Discard task preview
only closes the pending proposal. Completed/cancelled tasks cannot be reopened.

Reassignment immediately revokes the previous crew's task/inspection read and
completion access. The target crew waits for an explicit saved GA recalculation.
An affected old crew route is omitted with a stale/recalculation explanation;
unrelated still-valid stale routes retain existing completion behavior.

## Interfaces and preservation

Schema v6 adds task-change receipts, events and durable constraints; the v5 migration
preserves existing data/revision. Existing A task cancellation executes in the same
transaction as the change receipt. Input/task/configuration freshness and preview
expiry are checked. Repeated confirmation and bounded explicit replan retries are
idempotent. Public task-change DTOs use c-assistant-task-change-v1. Optional route
metadata and generated OpenAPI/TypeScript are updated; see [API contract](API_CONTRACT.md).

English UI, errors, documentation and generated answers are now consistent.
Multilingual question aliases still work. Captured historical JSON uses lossless
Unicode escaping with original/current hashes; it is not falsely translated and
presented as a new experiment. Word font metadata and personal account names are
not translated. The header displays username and English role. Knowledge v15 was
rebuilt into the ignored local Chroma index using cached E5 weights (61 passages).

Before automatic startup migration, a local SQLite backup was retained outside
the repository. Eight original business tables are byte-value equivalent, input
revision remains 7, and the new task-change tables are empty in the user's database.
All 14 pre-existing model-training working files match their recorded SHA-256.
Dataset, live/test databases, caches, credentials and temporary scripts are not
included in delivery. No model training or model-weight change occurred.

## Verification

| Check | Observed result |
| --- | --- |
| Frontend full Vitest suite | 15 files, 176 tests passed |
| TypeScript, ESLint and Vite build | Passed; existing large-bundle warning remains |
| RAG/knowledge/evidence/answer suites | 228 passed, 1 skipped because Windows test symlinks are unavailable |
| Routing core, GA, fixtures and GA evaluation | 56 passed |
| Backend task/availability/routing/workflow regression run | 130 passed before the final authorization regression |
| Task-change/auth run after authorization repair | 26 passed; one legacy migration fixture updated and rerun together with authorization case: 2 passed |
| Dedicated task-change cases | All 17 passed, including null travel, nonmetric cancellation, rollback, revision races, configuration drift and restart persistence |
| Real-auth isolated HTTP | Feasible move, idempotency, new-task affinity in both algorithms, overtime rejection, cancellation history/exclusion, role denial and pre/post-replan crew authorization passed |
| Browser, isolated real backend | Load, preview, confirm, replan, lock display, overtime rejection, cancellation and refreshed exclusion passed |
| Responsive check | 390x844 viewport; no horizontal overflow; readable stacked route cards |
| Real GPT (gpt-4.1-mini), two bounded requests | Chinese deep-pothole question returned English P1/240/high; later-recalculation question explained persistent constraints and explicit unassigned behavior; exact source/quote validation passed |
| Repository check and diff whitespace | Passed |

Test batches overlap and must not be added to claim a unique test count. No Google
billing call or new model training was performed. Synthetic travel acceptance does
not validate real Google travel times. These targeted GPT tests do not establish
universal semantic correctness.

[Sanitized executed evidence](../SystemCode/experiments/assistant/task-adjustments-20261021/acceptance.json)
includes HTTP results, English answers, exact evidence checks and preservation
results. [Desktop test view](../SystemCode/experiments/assistant/task-adjustments-20261021/task-routes-desktop.png)
and [mobile test view](../SystemCode/experiments/assistant/task-adjustments-20261021/task-routes-mobile.png)
show synthetic acceptance data, not the user's live task assignments.

Temporary acceptance servers on 8001/5174 were closed. The user's backend remains
on 8000; the frontend preview is available on 5173. The original dispatcher session
and read-only current-plan view were restored. Future-agent delegation preference
is recorded in the user's global AGENTS.md and this repository's AGENTS.md.
