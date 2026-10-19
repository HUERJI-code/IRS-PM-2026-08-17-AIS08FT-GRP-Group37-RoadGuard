> Archive: this retains the 2026-10-15 planning baseline and open work, rather than describing everything as currently unimplemented. Steps 1–9 are now implemented; README, VALIDATION.md and COMPARISON_GUIDE.md define actual validation. Steps 10–14 remain pending.

# RoadGuard: C implementation plan

Baseline: local groupwork1 main `f8a2cf37de91c09d86ec14e6cbd6045e83e421f8`, checked 2026-10-15. This was a plan; the steps below had not been executed when written.

C should deliver React pages, the four-crew map and GPT/RAG assistant, supporting photo upload through route viewing, explanation and confirmed crew changes. The seven C1–C7 work packages are divided into fourteen independently verifiable steps.

## Starting point

| Area | Repository state at planning | Implication |
|---|---|---|
| A backend | Upload/detection/review/task/image/revision/history APIs | Integrate rather than duplicate vision/rules |
| Released model | 19,218,837-byte weights match manifest/hash | Verify real mode with compatible dependencies; no retraining required |
| B dispatch | Crew service, Greedy/GA, saved plans, recalculation, optional Google matrix and experiments | Map/comparison can integrate; local acceptance still needed |
| Frontend | README only, no application/package.json | Begin foundations |
| Assistant | No roadguard/assistant or routes | Implement backend and UI |
| Knowledge | a-knowledge-v6, six documents, manifest, ten acceptance questions | Materials exist; no retrieval/index/generation |
| Report/video | Outlines, installation and requirements; no final report/video | Supply C chapters, screenshots, guide and recordings |

The inventory contained 275 tracked files: root 5, .github 9, Miscellaneous 33, ProjectReport 6, SystemCode 221 and Video 1. All paths/content were scanned. Direct C dependencies—guidance, contracts, models, crew/planning services and knowledge—received detailed reading. Other algorithms/training/tests received structural/purpose review; JSON/GeoJSON/CSV were parsed completely, fourteen images reviewed together and model metadata/SHA-256 checked. This was not a line-by-line audit of all 108 Python files, nor a model/full-test rerun. The initial file inventory remains in C’s local materials.

## Differences to resolve

1. Overview documents lag code: root README, AGENTS stage text, allocation and early API text still say B is pending despite registered routes/services. Plan against actual implementation and ask A/B to update shared status.
2. CrewService.update changes crew/global input only; PlanningService.recalculate is explicit. Task changes behave similarly. Distinguish changed data, pending planning, successful recalculation and failed recalculation.
3. Assistant confirmation needs atomic concurrency protection. CrewPatch checks crew expected_version but not preview input_revision and opens its own write transaction. An external precheck leaves a race. Step 12 requires A/B support for both checks inside the update transaction; C never writes B tables directly.
4. Knowledge qa-03 still requires review for every nonempty real result, conflicting with current workflow/tests/document 04: primary confidence ≥0.60 creates one task automatically. A must update question/content/package hashes before indexing. Other “B pending” text also needs revision. Hash consistency does not prove current content.
5. Return/shift settings are demo assumptions: project return policy remains null while B uses return=true and 480 minutes. Display saved settings with provenance; do not claim approved operational policy.
6. Old contracts/examples use a-dto-v1; real-auto-task-example.json retains v4 upload. Current v5 has four fields and review requires a detail read. Historical examples are not current mocks.
7. Google travel times do not supply road polylines. geometry=null allows only labelled stop-order schematic lines.

## Fourteen steps

Tests and guides accompany every step; step 13 adds cross-module acceptance rather than postponing all tests.

### 1. Integration inventory and page flow

Define upload/results, review, tasks, four-crew controls/routes, comparison and assistant. Map implemented A/B contracts/versions and normal/empty/failure examples. Draft assistant requests/responses. Record documentation conflicts, geography delivery, knowledge updates and confirmation transactions. Deliver PAGE_FLOW.md, API_MAPPING.md and OPEN_QUESTIONS.md. C leads UI/assistant; A owns shared contracts/content; B owns routes/crews. Every field needs a source and explicit dependency; ordinary pages need not wait for all assistant decisions.

### 2. Frontend foundation and local entry

Create React navigation, skeletons/layout under SystemCode/frontend. Match Node 22/npm CI and one package-lock. Add API proxy or agreed CORS; backend initially has no CORS middleware. Provide executable macOS instructions rather than Windows/CUDA training commands. Deliver app, environment example, lint/test:ci/build and meaningful foundation tests. Desktop/mobile navigation, real local health and CI scripts must work; real vision can be verified later with explicit demo first.

### 3. Shared client, types and mock mode

Wrap /api/v1, image URLs, error codes, operation IDs, revisions and time formatting. Provide explicit schema-validated mocks with visible provenance and shared loading/empty/no-plan/error/conflict states. Deliver shared types/methods/error components/current examples. Retry the same action key; changed content/resolved conflicts create new keys. No silent failure fallback. Keep business minutes, runtime milliseconds, UTC and Singapore display distinct.

### 4. Upload and results

Upload one JPEG/PNG with Jurong coordinates/road declaration using multipart image/metadata and Idempotency-Key. Distinguish real/demo; real omits scenario_id. Handle accepted/pending_review/no_detection. After the four-field upload result, read details/task for image_url, provenance, detection_id, record_version and rule evidence. Draw the unique box on server-normalised dimensions to avoid EXIF errors. Deliver form/location/results/box. Verify normal/no detection/low confidence, invalid location/image, 8 MiB/20 MP limits, unavailable inference and duplicate upload. No detection never means road safety; distinguish real inference and demo business rules.

### 5. Manual review

Pending queue/details support confirm, correct among eight shared labels, and dismiss. Send expected_version/request_id, valid detection_id for confirm/correct, damage_label only for correction. Preserve model evidence and review history. Only pending_review is writable; no duplicate tasks. After 409, reread/reassess rather than overwrite. Refresh tasks/route status after success.

### 6. Task management

List active/completed/cancelled tasks with location, damage, priority, duration, rule reasons/version. Complete/cancel or correct label/full location group; show history. Do not allow arbitrary priority/service_minutes/due_at. Final states retain history and cannot reactivate. Unknown duration/deadline is unknown/not set, never zero. Input changes warn of stale plans.

### 7. Crew controls and explicit recalculation

Read all crews and change availability. Use returned input_revision to explicitly recalculate paired GA/Greedy IDs. Read a snapshot when upload-created tasks need a revision. Share the replan entry across changes. Show disabled/idle crews. A crew save is not route success; retain actual saved state/stale old plans if Google/planning fails. Retrying planning must not repeat crew changes. Refresh conflicts before confirmation.

### 8. Jurong map

Use frozen JE/JW GeoJSON/NUS-ISS and include the external depot in bounds. Stable crew colours, ordered stops/lines, linked task/crew details, return legs, status and all unassigned reasons. Coordinate direction/order must match saved plans without omissions. geometry=null requires a stop-order/non-navigation label; distinguish Google/simulated travel.

### 9. GA/Greedy comparison

Prefer paired IDs from one recalculation. Display assigned/unassigned P1/P2/P3, travel/repair/makespan/workload/runtime/objective. Verify revision/start/settings/provenance; two latest plans alone are insufficient. Missing evidence suppresses improvement percentages; consider B batch/matrix IDs. Missing deadlines make lateness uncomputable; handle zero denominators. Objective improvement is not universal improvement/money saving. Identify Greedy-seeded online GA from algorithm_parameters and distinguish pure-GA historical experiments.

After steps 1–9, demonstrate upload → review/auto-acceptance → task → recalculation → four-crew map/comparison.

### 10. Knowledge cleaning, chunking and retrieval

Correct outdated knowledge/questions with A and release matching versions. Validate manifest hashes; chunk at stable anchors. Retain document_id, section_id, package/document/rule versions, classification and original sources. Choose retrieval proportionate to scale; embeddings depend on evidence/cost, not default complexity. Deliver ingestion/retrieval/citations/acceptance. Return relevant document_id#section_id, reject inconsistent sources, distinguish facts/demo assumptions/open decisions. Never explain/recalculate old rule_version tasks using the latest static rules.

### 11. Read-only GPT/RAG

Implement POST /assistant/query in the shared backend with retrieved knowledge and B’s saved plan_id. Explain order, assignment, unassigned reasons, metrics/rules; obtain task provenance through A services if needed. Return answer/sources/supported/version evidence and show plan/citations in UI. Missing evidence/plan must be explicit; stale plans labelled. No invented IDs/numbers/sources. GPT credentials/limits stay server-side. Treat retrieved text/questions as data, preventing instructions from executing business actions. Verify real calls separately from doubles.

### 12. Crew-change preview, confirmation, cancellation and recovery

Implement three proposed change-request/confirm/cancel endpoints, initially only one crew availability change. Persist concrete crew, old/new availability, based_on_plan_id, input_revision, crew version and lifecycle. Clarify ambiguous/unsupported requests instead of guessing.

With A/B, atomically check preview versions and update through domain services, then replan. C owns lifecycle persistence integrated through shared migrations. Contractually distinguish pending/executing/confirmed/cancelled/expired and updated-but-recalculation-failed. Deliver structured cards, three APIs, persisted status and before/after comparison. Preview/cancel never changes business data; stale previews fail; duplicate/concurrent confirms execute once; restart recovery can establish outcome. Keep business-save and calculation status separate; planning retry must not disable again. Current recalculate lacks idempotency ID, requiring a recovery protocol rather than claims based only on disabled buttons.

### 13. C and A/B/C acceptance

Use isolated database/images for full flows with mock, real backend, available real model and external failures. At least ten dynamic route questions and ten adjustment cases retain inputs/expected/actual/citations/versions/real-model status. A/B fix their own module defects. Deliver automation, end-to-end records, limitations and assistant evaluation. Run lint/test:ci/build, relevant Python and repository checks. Unrun paid APIs/models/devices remain explicitly unverified.

### 14. Guides, report, screenshots and video

Update frontend/assistant READMEs, macOS installation, user guide, variables and limitations. Supply design, retrieval/prompt constraints, confirmation and evaluation chapters. Use actual UI screenshots and C’s use-case/technical recordings for A’s final package. Another member must reproduce the demo. Team delivers two approximately five-minute videos; C coordinates recordings, A final package. Members narrate personally without AI speech. Reflections/peer evaluation remain individual/confidential submissions.

## Minimum acceptance set

| Area | Required cases |
|---|---|
| General | Loading, empty, error, mobile, duplicate clicks, timeout, Singapore time, live/mock provenance |
| Image/review | Upload/details, 0.60 boundary, low confidence, no detection, all review actions, normalised-image box, no duplicate tasks |
| Task/crew | Completion/cancel/correction history/revision; disable/restore/all unavailable; no-op; conflict |
| Routes | 0/1/fewer-than-four/10/15/20 tasks; four crews visible; every task assigned or reasoned; stale/missing/failure |
| Comparison | Same-run evidence, missing/zero values, runtime milliseconds/business minutes, noncomparability explanation |
| Knowledge | Supported/citable answers, refusal, old rules/stale plans, model failure, no instruction-driven actions |
| Changes | No write before confirm/on cancel; stale rejection; duplicate/concurrent confirm; post-write disconnection; restart; partial failure |

Ten suggested route questions: crew responsibilities; one crew’s order; why NUS-ISS; task arrival/completion; why unassigned; busiest crew; GA/Greedy metric comparison; stale-plan reason; Google provenance; lateness without deadlines. Each needs plan_id/citations; ten static knowledge questions do not substitute.

Ten suggested adjustments: disable a named crew; restore it; cancel; repeat confirmation; concurrent confirms; task change after preview; crew change after preview; already-target state; ambiguous/invalid crew; unsupported closure/direct priority change. Add matrix failure after committed crew change and restart recovery.

## Coordination

| Party | Align | Independent progress |
|---|---|---|
| A | Schemas/examples, qa-03/content, static geography/labels, assistant config/routes/migration | UI/client/labelled mocks/existing A pages |
| B | Crew/plans, two-stage results, atomic revisions, retries, same-run evidence | Read plans/maps/crews/current recalculation |
| A/B | Demo shift/return/weights, integration data/replan UX | Display current saved settings with provenance |
| User/owner | GPT config/budget, map provider, real-call acceptance | No-cost UI/doubles |

Define each step’s acceptance and commit scope. Start short-lived feature/c-* from clean synced main; shared changes document caller impact. PRs are English; incomplete/review-only PRs remain Draft. Historical auto-merge guidance does not authorise pushing this plan.

## Sources and review limits

Root: groupwork1. Relative sources: AGENTS.md (ownership/services/confirmation/citations/tests); Miscellaneous/TEAM_WORK_ALLOCATION.md sections 4/7/10 (C1–C7/four assistant routes/20 cases); API_CONTRACT.md (A v5/snapshots/B); backend api/workflow.py and schemas/workflow.py; crews/service.py:78; routing/service.py/models.py/README.md; knowledge/manifest.json, six documents and acceptance_cases.json:88; SystemCode/contracts and config; .github/workflows/ci.yml and scripts/check_repository.py; SystemCode/tests; ProjectReport, Video and SUBMISSION_CHECKLIST.md. Existing tests do not imply executed tests.

This planning review inventoried/scanned/parsed files, read key dependencies, reviewed images and checked knowledge/model hashes. It did not install dependencies, start apps, call GPT/Google, change business code or run full tests. Workspace stayed clean. Planning/inventory initially remained in Codex outputs rather than the team repository.
