# RoadGuard three-person work allocation and interface handoff

Prepared: 2026-10-11; status updated: 2026-10-21. Vision, rules, persisted workflows, four-crew planning and the authenticated frontend are implemented; see the [integration record](INTEGRATION_ACCEPTANCE_20261018.md), [frontend guide](../SystemCode/frontend/README.md) and final report contribution table. ChromaDB/E5 retrieval, optional query-v3 English grounded answers and persistent confirmed task adjustments are implemented. Targeted real GPT cases passed; broad answer-quality evaluation and presentation videos remain pending. The work packages below retain the original allocation and acceptance targets; they are not a claim that every planned deliverable is complete.

All members and agents follow root [AGENTS.md](../AGENTS.md). This table maintains detailed responsibilities and draft interfaces; the shared rules maintain collaboration and verification requirements.

Project scope: Jurong East and Jurong West, Singapore; one simulated maintenance department; four crews; shared NUS-ISS simulated origin outside the task area; single-photo input; RDD2022ES/YOLO; rules and human review; GA and Greedy; React website; GPT + RAG route assistant. Assistant implementation and targeted acceptance are delivered; broader evaluation remains outstanding. Geographic evidence and integration requirements are in the [scope/depot document](JURONG_SCOPE_AND_DEPOT.md).

A is Hu Erji (project initiator); B is Yan GuanTing; C is Wu TaoYi. At your request, A carries more work, including backend foundations, business data and system integration, so B can focus on routes and C on UI/assistant work. Unless explicitly implemented or frozen, the following interfaces and acceptance criteria are future-development agreements.

## 1. Overall responsibilities

| Member | Main responsibility | Additional work/boundary | Final deliverables |
| --- | --- | --- | --- |
| **A: Hu Erji** | Vision, confidence routing, rules, inspection review and tasks | Shared backend/database, knowledge/demo data, interface/integration/report/submission coordination | Detection/business APIs, model/evaluation, rules, task database, examples and reproducible integrated workflow |
| **B: Yan GuanTing** | Four-crew dispatch, travel matrix, Greedy, GA, route evaluation | Crew/routing APIs; consume A's standard tasks; results usable directly by C | Independently runnable routing, crew/planning APIs, metrics, GA comparisons and algorithm chapter |
| **C: Wu TaoYi** | React, map, GPT/RAG assistant | Assistant in A's backend; A supplies knowledge, B route facts; do not reimplement priorities/routes | Website/map/assistant APIs and interactions, guide, UI/assistant tests and recordings |

Each member owns module tests, usage documentation and report chapters. A compiles/integrates; module owners still fix defects.

## 2. A's work packages: vision, rules and backend foundation

| ID | Module | Tasks | Deliverables | Completion/integration criteria |
| --- | --- | --- | --- | --- |
| A1 | Requirements/shared data | Jurong boundary, simulated depot, eight labels, task fields/statuses/units, thresholds/versions; API documentation | Scope, field dictionary, configuration, request/response examples | Shared B/C fields; unknown parameters explicit, not independently guessed |
| A2 | Data preparation | Verify RDD2022ES source/labels; class counts; train/validation/test splits; originals/mirrors together | Scripts, split manifests, label table, provenance | Reproducible, no mirror leakage; no claim of local Jurong training images |
| A3 | YOLO training/inference | Train/validate/infer; boxes/classes/confidence; annotated previews; explicit mock detection for early integration | Entry points, weight locations, examples | B/C can use mocks before training, then switch to real model |
| A4 | Confidence/rules | Automatic acceptance versus review; class mappings to severity, P1/P2/P3, repair advice/duration | Configuration/service, triggered rules/versions | Consistent inputs/outputs; corrections use same rules; validate threshold before finalizing |
| A5 | Inspection/review | Image/location intake; save/query/confirm/correct/dismiss; no detection/invalid input | Upload/query/review APIs, annotated-image access | High confidence queued; low confidence creates no active task before confirmation; no duplicate on retry |
| A6 | Tasks/database | Create/query/complete/cancel; label/location correction; data/revisions | SQLite definitions, APIs/query service | Provenance per task, rule priorities, completed/cancelled excluded from planning |
| A7 | Shared backend | FastAPI entry/configuration/DB/errors/storage/route registration/startup | Foundation/shared modules | B/C integrate without separate services; server-side secrets |
| A8 | Knowledge/demo data | Priority/repair/operation knowledge; review cases, Jurong synthetic tasks; C's RAG sources | Checked knowledge, normal/edge cases, fixed sets | Sources/versions explicit; synthetic tasks separate from real photo provenance; shared B/C examples |
| A9 | Integration/experiments/delivery | Connect inspection/tasks/planning/UI; model/rule evaluation; end-to-end tests; report/package | Results, integration record, report/checklist | Reproducible complete demo, clear failure feedback, no old-project results |

A to B: standard Tasks, study boundary/depot, repair-duration/deadline definitions, queue revisions/change notifications and fixed experiments.

A to C: inspection/review/task APIs, detection/annotation examples, shared errors, rules/repair knowledge and UI field definitions.

## 3. B's work packages: four-crew routes and optimization

| ID | Module | Tasks | Deliverables | Completion/integration criteria |
| --- | --- | --- | --- | --- |
| B1 | Crews | Four by default; IDs, availability, origins, shifts; identical capability recommended initially | Model/query/availability APIs | Four visible; unavailable unassigned; idle retained |
| B2 | Travel matrix | Task/depot nodes, Google times, reproducible mocks, failures/provenance | Provider, node mapping, source metadata | Ordered rows/columns, asymmetric support; unreachable not zero |
| B3 | Greedy | Explainable initial assignment/order; same constraints as GA | Planner/documentation | Each assigned task once; unassigned reasons |
| B4 | Group-built GA | Chromosomes, population, selection, crossover, mutation, repair, elitism, stopping; assignment/order | Planner/configuration/fitness/constraints | Valid four-crew plans, reproducible seed; no assumed superiority |
| B5 | Planning/recalculation | Query A's tasks; both algorithms; save; recalculate after task/crew changes | Services/query/plans/input revisions | Updated plans; old plans explicitly stale |
| B6 | Metrics/experiments | Travel/repair/lateness/workload/unassigned/runtime; 10/15/20 tasks | Raw tables/charts/reproduction | Four crews, same inputs/matrix, multiple seeds; runtime separate from API wait |
| B7 | Algorithm/video | Encoding/objective/constraints/results/limits; before/after routes | Report chapters/technical demo | Evidence-backed conclusions; computation/completion/cost distinguished |

B to A: planning API, crew-update service, recalculation status/errors, objective/metric definitions.

B to C: query API, ordered stops, four-crew metrics, unassigned reasons, plan ID/provenance; geometry when available, otherwise explicit schematic convention.

## 4. C's work packages: frontend and GPT/RAG

| ID | Module | Tasks | Deliverables | Completion/integration criteria |
| --- | --- | --- | --- | --- |
| C1 | Foundation | React/navigation/shared API/loading/empty/error; desktop/mobile | Project/components/pages | Independent mock development then real APIs |
| C2 | Inspection/review | Upload/location/class/confidence/box; confirm/correct/dismiss | Submission/results/review queue | Follow A's status, refresh tasks, no arbitrary frontend priorities |
| C3 | Tasks/crews | Status/rules; complete/cancel; four crews/availability | List/details/configuration | Display backend/recalculation results; no second browser business state |
| C4 | Map/comparison | Crew colors, depot/order, GA/Greedy metrics, unassigned/stale | Map/details/comparison | B's order; schematic is not road navigation; mock/Google distinction |
| C5 | GPT/RAG | Retrieve A's documents; B's facts; citations; unsupported questions | Backend/retrieval/answer API | Traceable knowledge/plan; no direct model writes to priorities/routes |
| C6 | Change requests | Initially availability; structured preview/confirm/B recalculation | Preview/confirm/cancel APIs/UI/explanation | No pre-confirmation mutation/repeated execution; stale preview regenerated |
| C7 | Verification/guide/demo | Test UI/assistant; guide/screenshots; recording coordination | Q&A/UI records/guide/video | Normal/error demo; actual screenshots; owners supply portions |

C to A: UI fields, API error cases, missing knowledge, frontend/assistant results.

C to B: map/metric requirements and confirmed structured crew changes.

## 5. Code/shared-file ownership

Paths follow the current `roadguard` package. A owns shared directories; owners maintain their modules. Unimplemented paths remain proposed ownership. Synchronize interface examples/docs when changing another member's interface.

| Path/content | Owner | Integration |
| --- | --- | --- |
| `SystemCode/model/` | A | Shared Detection output |
| `SystemCode/backend/roadguard/main.py`, configuration/DB/errors | A | B/C routers centrally registered by A |
| `SystemCode/backend/roadguard/vision/`, `rules/`, `inspections/` | A | inspections owns inspection/linked-task transactions; outputs reviews/tasks without requiring model internals |
| `SystemCode/backend/roadguard/crews/`, `routing/` | B | Implemented crew/plan services using A's consistent task snapshots |
| `SystemCode/backend/roadguard/assistant/` (implemented) | C | A/B facts; confirmed domain-service changes, no direct table writes |
| `SystemCode/frontend/` | C | API business conclusions |
| `SystemCode/backend/knowledge/` | A content/C retrieval | A reviews rules; C indexes/retrieves/cites |
| DB tables/init/migration | A coordinates B/C definitions | One shared-entry maintainer avoids simultaneous initialization edits |
| Dependencies/config/deployment | A coordinates B/C needs | One environment/application entry |
| `SystemCode/experiments/`, tests | Each owner; A compiles | A vision/rules; B dispatch; C assistant/UI |
| `ProjectReport/`, `Video/` | A compiles all members | Do not place all reporting/recording on C |

## 6. Shared data: initial freeze and later drafts

2026-10-12: A's initial `Detection`, `Inspection`, `Task`, `DecisionTrace`, `ErrorResponse`, `HealthResponse`, `PlanningRevision` are implemented. The [API contract](API_CONTRACT.md) and linked schemas are the sole maintenance point for fields/constraints/versions/examples; this table avoids duplication. B/C start from those fixtures. Other objects remain drafts; all M0 is not frozen.

Shared conventions: string IDs; `latitude`/`longitude`; confidence 0–1; travel/repair minutes; timezone-aware ISO 8601 API timestamps, preferably UTC with Singapore display. RDD2022ES v1 eight IDs were checked against release notes and packaged `classes.txt`; use the [label dictionary](../SystemCode/model/label_schema.json). Severity/priority mappings remain; P3/P2/P1 simulated durations finalized 2026-10-14 are 60/120/240 minutes. The [baseline](BUSINESS_RULES_BASELINE.md) is not a real engineering standard.

| Object | Provider → consumer | Minimum fields | Agreement |
| --- | --- | --- | --- |
| **Detection / Inspection / Task** | A → B/C | [Contract](API_CONTRACT.md) | Original DTO/a-workflow-v2 records implemented; live workflow uses demo rules |
| **Crew** | B → A/C | `crew_id`, `name`, `available`, origin coordinates, `shift_minutes` | Four fixed IDs; unavailable/idle retained; no initial capability differences |
| **PlanningInput** | A/B → B | `input_revision`, `planning_start_at`, `tasks`, `crews`, shift/return settings, objective weights, `random_seed` | Consistent batch; shared revision update after task/crew changes |
| **TravelMatrix** | B internal; summary A/C | `node_ids`, `duration_minutes`, `provider`, `generated_at` | i,j means i→j; asymmetric; null unreachable explicitly handled; same GA/Greedy matrix |
| **RoutePlan** | B → A/C | `plan_id`, `input_revision`, `algorithm`, `planning_start_at`, `crew_routes`, `unassigned_tasks`, `metrics`, `matrix_provider`, `is_stale` | `ga`/`greedy`; four crews; unassigned IDs/reasons; query saved ID |
| **CrewRoute / Stop** | B → C | Crew ID, ordered tasks, coordinates, relative arrival/completion minutes, travel/repair/total, optional geometry | Count depot-to-first; return by finalized policy; labeled schematic without geometry |
| **Explanation** | C → frontend | `plan_id`, `answer`, `sources`, `supported` | Prefer matching plan/A knowledge; state insufficient evidence |
| **ChangeRequest** | C → frontend/B | `request_id`, `based_on_plan_id`, `input_revision`, `type`, structured parameters, `status`, post-confirmation `result_plan_id` | Implemented crew availability and task reassignment/cancellation via preview/confirm; persistent crew constraints survive recalculation; no mutation solely from natural language |

Schemas validate stable detection IDs, selected objects, demo sources and UTC. Demo samples do not establish formal priorities/durations.

### Route metrics

| Metric | Proposed definition | Owner |
| --- | --- | --- |
| Total travel | Sum across crews including NUS-ISS to first task; return according to finalized policy | B |
| Overall completion | Common start until last crew finishes | B |
| Lateness | `max(0, completion_at - due_at)` for deadline tasks; also late count | A deadlines; B calculation |
| Workload balance | Standard deviation of travel+repair across available crews, including idle as zero | B; A business meaning |
| Algorithm runtime | Planner itself; separate matrix/API preparation | B |
| Unassigned | Tasks outside all routes and reasons; no omission | B |

These are proposed comparison definitions to freeze. B proposes fitness weights/normalization for A to review; do not label these actual monetary savings.

## 7. HTTP responsibilities

Prefix `/api/v1`. Health, `/demo` previews, inspection/review/tasks, crews and persisted route plans are implemented; see the [contract/errors](API_CONTRACT.md) and [routing guide](../SystemCode/backend/roadguard/routing/README.md). The assistant rows below are proposed interfaces, not registered endpoints. Business API access follows the current [account permissions](ACCOUNT_ROLES.md).

| Endpoint | Owner | Caller | Input | Output/behavior |
| --- | --- | --- | --- | --- |
| `GET /health` | A | C/startup | None | Availability; no fabricated model/API readiness |
| `POST /inspections` | A | C | Image/demo case/coordinates/road declaration/idempotency key | a-workflow-v5 compact inspection_id/status/detection/task_id; obtain planning revision separately |
| `GET /inspections?status=...` | A | C | Filter | Inspection/review list |
| `GET /inspections/{id}` | A | C | ID | Detection/images/review/rules |
| `POST /inspections/{id}/review` | A | C | `confirm`/`correct`/`dismiss`, request/expected revision, selected detection for confirm/correct | pending_review only; unique task for confirm/correct, none for dismiss; raw/history retained |
| `GET /tasks?status=...` | A | C | Filter | Tasks/current revision |
| `PATCH /tasks/{id}` | A | C | Request/expected revision, complete/cancel, label/full-location correction | TaskMutation/revision; no arbitrary priority/fake recalculation |
| `GET /crews` | B | C/A | None | Four crews |
| `PATCH /crews/{id}` | B | C; future assistant confirmation | request_id, expected_version, available | Updated crew/input_revision/planning_input_changed/replayed; no automatic recalculation |
| `POST /route-plans/recalculate` | B | A/C | Current saved data/expected revision | Same-input GA/Greedy IDs/status |
| `GET /route-plans/latest?algorithm=...` | B | C | `ga`/`greedy` | Latest plan/no-plan and staleness |
| `GET /route-plans/{id}` | B | C/assistant | ID | Saved display/explanation/comparison facts |
| `POST /assistant/query` | C | Frontend | Question/plan ID/optional comparison ID | Sourced Explanation; backend reads facts |
| `POST /assistant/change-requests` | C | Frontend | Natural-language request/current ID | Pending request, no mutation |
| `POST /assistant/change-requests/{id}/confirm` | C | Frontend | Explicit confirmation | Check revision, execute/recalculate through B, new ID |
| `POST /assistant/change-requests/{id}/cancel` | C | Frontend | Request ID | Cancel pending, no business change |

Register fixed `latest`/`recalculate` before dynamic `/{id}`. Shared health URL is `/api/v1/health`.

The initial assistant changes only availability to reduce C's workload. Urgent new tasks use A's inspection/review/rules. Closures/detours/direct order edits are later extensions, outside initial acceptance without three-member confirmation.

### Internal interfaces: avoid HTTP duplication of business data

| Service | Provider | Consumer | Integration |
| --- | --- | --- | --- |
| VisionService | A | A inspections | Explicit synthetic DemoDetector; real-image/released-model LocalVisionDetector; separate sources |
| RuleService | A | A task/review; C read-only trace | Persisted; raw retained; explicit human mapping/frozen inspection rules |
| TaskQueryService (implemented) | A | B; future C assistant | snapshot(expected_revision=None, *, connection=None) returns all active Tasks/revision in one transaction; PlanningService uses the shared connection for crew reads; [handoff](BC_HANDOFF.md) |
| Shared input revision (formerly draft PlanningRevisionService) | A | A/B | Task mutation increments same transaction; B follows for crews; [backend](../SystemCode/backend/README.md) |
| PlanningService | B | A/C confirmation | Generate/save both algorithms from current tasks/crews |
| CrewService (implemented) | B | B API; future C confirmation | Validate/update availability with expected_version; return revision for a separate explicit recalculation |
| RouteQueryService | B | C assistant | ID → saved facts/metrics |
| KnowledgeRetrievalService (implemented C) | C | C assistant | Question/context → versioned passages/sources; [a-knowledge-v15](../SystemCode/backend/knowledge/README.md) has eleven documents and 30 synthetic acceptance specifications, not executed RAG results or engineering approval |

Owners add function signatures on freeze. A inspections and C assistant call B's service rather than duplicate dispatch algorithms.

## 8. Integration cases and acceptance

| Scenario | A | B | C | Acceptance |
| --- | --- | --- | --- | --- |
| High confidence | Detection/rules/task/recalculate after save | Queue/four-crew plan | Display result/task/routes | Rule source; assigned once if feasible, otherwise reason |
| Low confidence | Review, no active task before confirmation | Exclude before, recalculate after | Review/status | Confirm/correct/dismiss follow rules |
| Complete/cancel | Queue/revision | Remove from new plans | Refresh | History retained, no new resource use |
| Unavailable crew | Stable tasks/revisions | Disable/reassign/unassigned | Management or confirmed assistant | Four visible; no new tasks for disabled crew |
| Explanation | Rules/knowledge | Facts/metrics | Retrieve/answer/cite | No inventions; identify plan |
| API/model failure | Mode/errors; accepted data retained | Source clear; old plan stale on failure | Clear failure/mock notice | No old-as-current/mock-as-real |
| Repeated review/confirm | No duplicate task | Deterministic update/recalculation | Execute once | No duplicate tasks/mutations/inconsistency |

Shared/base errors are in the [contract](API_CONTRACT.md); new business codes in the same PR, not natural-language matching.

## 9. Delivery: agree interfaces, then develop in parallel

| Stage | A | B | C | Exit condition |
| --- | --- | --- | --- | --- |
| M0: freeze | Label/task/review samples, DB conventions, scope/rules | Crew/input/plan examples, metrics/constraints | UI fields, assistant request/answer examples | Shared examples; open decisions owned |
| M1: independent | Backend/mock/rules/tasks; training preparation | Fixed-data Greedy, then GA | Mock pages/four-crew map | Independent demos, matching interfaces |
| M2: integration | Inspection/review/tasks/planning | Algorithms/crews/recalculation | Real APIs/core operations | Upload → review/accept → task → routes |
| M3: model/assistant/experiments | Real model, confidence/rules, knowledge | Same-input experiments/seeds/metrics | GPT/RAG/confirmation/tests | Three capabilities have functionality/evidence |
| M4: delivery | Regression/report/package | Algorithm/results/conclusions | Guide/screenshots/recordings | Reproducible guide, two consistent videos |

A prioritizes formats/mock detection/backend; training can run in parallel. B uses fixed tasks without waiting for training; C uses agreed mock responses without waiting for all backend. Update examples/docs and notify affected members on changes.

## 10. Each member's acceptance materials

| Member | Minimum deliverables |
| --- | --- |
| A | Dataset/splits; training/inference; weight access; per-class metrics; confidence evaluation; 20–30 normal/edge rule cases; inspection/review/task APIs; backend/startup; mock/knowledge; integration; report |
| B | Task/route examples; matrix/source; Greedy/GA; encoding/objective/constraints; validity tests; four crews, 10/15/20 tasks, multiple seeds; raw/charts; guide; report |
| C | Frontend startup/six page-area types; mock switching; map; GPT/RAG/sources; preview/confirm; 10 route questions and 10 change requests including unsupported/stale/repeated; guide/screenshots/video |

A edits the report; A/B/C own their results and technical chapters. Two approximately five-minute videos cover business/use cases and design/technical explanation. All supply their portions, C coordinates recording, A final files. Use members' own narration, not AI speech, under current course requirements.

## 11. Business options for joint confirmation

Jurong/NUS-ISS were recorded 2026-10-12 as geography baseline; simulated durations finalized 2026-10-14. Unconfirmed dispatch options remain drafts for A/B. Geography completion does not complete M0.

| Item | Proposed initial treatment | Lead |
| --- | --- | --- |
| Boundary/origin (recorded) | JE/JW URA MP2025; NUS-ISS outside area; [scope](JURONG_SCOPE_AND_DEPOT.md) | A versions, B vehicle access, C display |
| Capability/shifts | Four identical crews/shared depot/common configurable shift; configured return policy | B proposes/A confirms |
| Multi-detection task count (confirmed) | Model-selected primary ≥0.60 creates one; one HTTP box; raw candidates saved | A maintains/C integrates |
| No detection | Save inspection, no repair task | A |
| Threshold (confirmed) | Primary ≥0.60 auto-task, below review; uncalibrated | A |
| Duration (final)/deadline (pending) | demo-rules-v2 P3/P2/P1=60/120/240; due_at null; duration is not deadline | A maintains/B reads saved |
| Planning semantics | Common-start active-task replanning/simulation; no live tracking/executed-route locks | A/B |
| Assistant scope | Availability only initially; factual explanation; standard new-task workflow | C proposes/A/B review |
| Actual/schematic path | Road geometry if available; labeled schematic for point matrix | B/C |

Freeze unresolved options before corresponding implementation. Authorized shared backend/data foundations may proceed. Initial formats do not automatically approve assumptions.

## 12. Existing materials

- [Current scope](PROJECT_SCOPE.md)
- [Jurong/NUS-ISS](JURONG_SCOPE_AND_DEPOT.md)
- [Dataset/eight labels](DATASET_AND_LABEL_AUDIT.md)
- [Implementation plan](IMPLEMENTATION_PLAN.md)
- [Submission checklist](SUBMISSION_CHECKLIST.md)
- [Course mapping](../ProjectReport/COURSE_MAPPING.md)

Rules/workflow, evolutionary optimization, vision and natural-language cognition each need functionality/evidence. Contracts/backend foundations do not mean those capabilities/evaluations are complete.
