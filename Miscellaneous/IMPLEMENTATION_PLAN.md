# Implementation plan

The shared backend, explicit demo detection/rules, persisted inspection/review/task workflow and A's B/C task/knowledge handoff are implemented; the complete application milestones below remain pending or partial.

Step 1 geography is documented as of 2026-10-12: [Jurong East/West boundary and NUS-ISS simulated origin](JURONG_SCOPE_AND_DEPOT.md), with static GeoJSON and matching example configuration. The geographic step alone did not freeze task contracts, business rules or routing constraints; subsequent A deliveries are listed below and still do not complete M0.

A's preparation step 2, [dataset and label verification](DATASET_AND_LABEL_AUDIT.md), records the source version, eight class IDs, full archive-directory counts and targeted sample checks. Step 8 now provides full content validation, class-frequency statistics and grouped split manifests; actual bounded training and recovery evidence is tracked in [Step 8 acceptance](STEP8_VISION_ACCEPTANCE.md).

The authorized [30-epoch n/s follow-up](VISION_30_EPOCH_COMPARISON.md) is complete: validation error analysis, both independent training runs, CPU comparison and selected-model HTTP acceptance. YOLO11s wins the preregistered validation ranking; business accuracy and confidence calibration remain pending.

The [balanced Precision/Recall follow-up](BALANCED_VISION_OPTIMIZATION.md) completed 40 additional fine-tuning epochs, four-candidate threshold comparison, checkpoint/data verification and selected-model HTTP acceptance. Correct-eight-type Precision/Recall improved modestly to 50.5% / 52.0% at confidence 0.25 and IoU 0.5. The simultaneous 70% accuracy target remains open; this completed experiment does not close model-quality acceptance or establish every damage type improved.

## A's agreed work sequence

This sequence is the project owner's personal task list. Its step numbers differ from the whole-project milestones below.

| Step | A's deliverable | Current status |
| --- | --- | --- |
| 1 | Confirm Jurong boundary and shared simulated depot | Documented: JE/JW and NUS-ISS |
| 2 | Verify dataset version and labels | Source, directory and targeted sample audit complete; full preparation delivered in Step 8 |
| 3 | Freeze initial Detection/Inspection/Task, errors and revision contracts with fixed samples | Implemented; see [API contract](API_CONTRACT.md) and [examples](../SystemCode/contracts/README.md) |
| 4 | Shared backend entry, configuration, SQLite, errors, schemas and router registration | Implemented; [backend guide](../SystemCode/backend/README.md), health endpoint and automated tests |
| 5 | Explicit demo detector and confidence/business rules | Implemented for named synthetic scenarios with configurable demo assumptions; see [demo guide](DEMO_DETECTION_AND_RULES.md). Production calibration remains pending |
| 6 | Image upload, inspection/review and task CRUD workflow | Implemented in explicit demo mode: upload, polygon check, declared road type, persistence, review, task edits/status, idempotency and transactional revision; see [workflow guide](INSPECTION_REVIEW_TASK_WORKFLOW.md) |
| 7 | Stable task query input for B and reviewed knowledge for C | Delivered: consistent TaskSnapshot service/API, reproducible 10/15/20-task inputs, versioned source-checked knowledge and actual HTTP consumer example; see [B/C handoff](BC_HANDOFF.md). Review is repository consistency checking, not expert approval |
| 8 | Train/evaluate and integrate the real vision model | Data/preparation, checkpointed training/evaluation and opt-in real workflow implemented; see [actual acceptance evidence](STEP8_VISION_ACCEPTANCE.md). Calibration and business accuracy acceptance remain pending |
| 9 | Integrate A/B/C workflows and validate failure cases | A preparation delivered: [simulation rule baseline](BUSINESS_RULES_BASELINE.md) and [acceptance checklist](INTEGRATION_ACCEPTANCE_CHECKLIST.md); B/C integration deferred until their modules are ready |
| 10 | Complete reports, evaluation evidence and submission | Pending |

Steps 3/4 do not freeze business mappings, implement review/task APIs or complete M0. The fixture severity/priority/duration values remain simulation assumptions; the course baseline was finalized as demo-rules-v2 on 2026-10-14 with P3/P2/P1 service times of 60/120/240 minutes. This does not settle scheduling constraints or establish measured engineering values.

Step 5 remains a stateless detector-to-rule preview. Step 6 adds the persisted workflow using the same explicit demo assumptions, without real image inference. Polygon checks are implemented; road eligibility is declared by the caller, not independently verified. Step 7 delivers task/knowledge inputs; actual planning, knowledge retrieval/generation and production calibration remain pending.

## Whole-project milestones

See [the three-person work allocation and interface draft](TEAM_WORK_ALLOCATION.md) for ownership: A (project owner) leads vision, rules, backend foundations and integration; B leads four-crew routing; C leads the frontend and assistant. These are planned responsibilities, not completed contributions.

| Step | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 1 | Confirm study boundary, depot, task model and routing constraints | Written scenario and consistent configuration |
| 2 | Backend/frontend startup, database schema and four-crew configuration | Backend, infrastructure and A-owned inspection/task tables implemented; frontend and crew records pending |
| 3 | Image upload, labelled demo detector, confidence gate and rules | Implemented: one displayed box, compact upload, real primary confidence >=0.60 creates one task; lower confidence requires review; simulation rules v2 finalized |
| 4 | Task queue, travel-time provider and greedy planner | Valid routes and explicit handling of unassigned tasks |
| 5 | Group-built GA and automatic replanning | Valid four-crew routes, deterministic seeded checks and queue-change demonstration |
| 6 | RDD2022ES training/evaluation and real detector integration | Held-out metrics and documented dataset splits |
| 7 | Proposed GPT/RAG explanation workflow | Grounded answers; confirmed changes routed through the backend planner |
| 8 | Comparative experiments and end-to-end validation | Reproducible results and documented limitations |
| 9 | Final report, user guide and two videos | Completed submission checklist |

Start implementation after the repository structure and current scope have been reviewed. Each milestone should add runnable behavior and its necessary checks rather than pre-populating success claims.
