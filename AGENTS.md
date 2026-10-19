# RoadGuard project and agent collaboration rules

Version: 1.17 · Updated: 2026-10-18 · Applies to every directory in this repository, all three team members and their coding agents.

This is the shared entry point for project development rules. Members should use the same repository version and have their agents read this file before starting a task. Detailed responsibilities and draft interfaces are in [TEAM_WORK_ALLOCATION.md](Miscellaneous/TEAM_WORK_ALLOCATION.md); they must not depend on one member's chat history.

## 1. Current stage and authorization

- A's Steps 3–7 are complete. Step 8 implements full-data preparation, resumable training/evaluation and real detection integration; actual execution acceptance is recorded in the [Step 8 record](Miscellaneous/STEP8_VISION_ACCEPTANCE.md). The real model remains experimental. A real primary box meeting the configured confidence threshold (default 0.60) automatically creates one task; lower confidence requires review. Business rules remain demonstrative. Four-crew dispatch, the frontend and GPT/RAG services are pending.
- Implement only the task explicitly assigned by the human. Authorization to build the foundation does not authorize implementing the entire project at once.
- When the user requests explanation, review, planning or documentation, deliver that result without also creating business code, installing runtime dependencies, starting training or calling paid services.
- Complete routine implementation, local fixes and necessary verification within the authorized scope independently. Ask a specific question only when a critical business decision is missing, the scope must expand or an action has destructive effects; continue work that can be completed independently.
- This file defines project conventions and does not override system requirements of tools or platforms. Record explicit human changes to existing project decisions and their effects; A coordinates changes to conventions shared across members.

## 2. Before every task

1. Confirm that the working directory is this repository. Inspect the Git branch, existing workspace changes and applicable local instructions, preserving other members' work.
2. Read this file, the [project scope](Miscellaneous/PROJECT_SCOPE.md), [three-person allocation](Miscellaneous/TEAM_WORK_ALLOCATION.md) and the relevant module README.
3. For milestones, read the [implementation plan](Miscellaneous/IMPLEMENTATION_PLAN.md); for default scenarios, the [example configuration](SystemCode/config/project.example.json); for delivery, the [course mapping](ProjectReport/COURSE_MAPPING.md) and [submission checklist](Miscellaneous/SUBMISSION_CHECKLIST.md).
4. State whether the task represents A, B or C, its objective, intended modules, interface dependencies and acceptance method. Adopt the role directly when the task makes it clear; clarify an unclear scope first.
5. Check that documentation agrees with actual code. Explain conflicts rather than silently choosing one version or promoting historical proposals or simulated examples into confirmed requirements.

Shared business decisions follow the project scope and confirmed changes; module ownership follows the allocation table; this file governs collaboration. The [separate API contract](Miscellaneous/API_CONTRACT.md) and its linked shared schemas are the single maintenance location for the first DTOs, errors and version fields. B/C planning, crew and assistant objects and HTTP requests that are not yet frozen remain drafts in the allocation table. Freezing the initial set does not mean all of M0 is complete.

## 3. Confirmed project baseline

| Item | Shared requirement |
| --- | --- |
| Project | RoadGuard; AIS08FT; Group7; course start date 2026-08-17 |
| Geography | Jurong East and Jurong West, Singapore; frozen URA MP2025 boundaries, as defined in the [scope and depot document](Miscellaneous/JURONG_SCOPE_AND_DEPOT.md) |
| Dispatch scenario | One simulated maintenance department and four crews by default; shared NUS-ISS simulated origin, explicitly permitted outside the task area; no claim to represent real maintenance operations |
| Main workflow | Single image and location → detection → confidence routing/human review → business rules → valid task → four-crew planning → map and explanation |
| Technical direction | React; Python/FastAPI; SQLite; YOLO/RDD2022ES; Google travel-time data; a group-built GA; Greedy baseline; GPT + RAG assistant |
| Dataset labels | `juusos/rdd2022es` version 1; all eight class IDs 0–7 verified against the [shared label dictionary](SystemCode/model/label_schema.json); full preparation and grouped splitting implemented, as recorded in Step 8 acceptance |
| Main evaluation | Four crews and 10/15/20 tasks; GA and Greedy use identical inputs, travel matrices and constraints |
| Development baseline | Rebuild from the current course scaffold; do not migrate code or historical experimental results from the abandoned prototype |

Default crew IDs are `crew-01` through `crew-04`, matching the example configuration. Pass the crew count through configuration/input rather than hardcoding the old two-crew proposal. Changes to the main experimental scenario require corresponding scope and evaluation updates.

On 2026-10-13, it was confirmed that a photo typically has one main damage type and one main subject; no detection, multiple objects and uncertainty remain possible. The user further confirmed that day that the interface returns at most one box: a selected primary box with raw confidence ≥ 0.60 automatically creates one task; lower confidence awaits review, and no detection creates no task. Do not delete raw evidence or describe the threshold as an accuracy guarantee. After [single-target optimization](Miscellaneous/SINGLE_DAMAGE_OPTIMIZATION.md), the user explicitly authorized [publishing the best weights and integrating them into the backend](Miscellaneous/MODEL_RELEASE_AND_BACKEND.md). The default uses the release manifest. An a-workflow-v5 upload returns only inspection_id, status, detection (one object or null) and task_id; details retain one box, complete provenance and auto_acceptance, with matching a-knowledge-v5 documentation. The database retains raw evidence and the eight class meanings are unchanged. Image-type metrics must remain separate from box-detection metrics; neither of the two 70% targets has been met.

On 2026-10-14, the user finalized the course-simulation rules `demo-rules-v2`: the eight severity/priority mappings remain unchanged; expected repair durations for P3/P2/P1 are 60/120/240 minutes. Keep is_demo=true and do not present them as engineering standards. See the [business-rule baseline](Miscellaneous/BUSINESS_RULES_BASELINE.md) and [integration acceptance checklist](Miscellaneous/INTEGRATION_ACCEPTANCE_CHECKLIST.md). Existing inspections and tasks retain their frozen rules without bulk recalculation; B reads each saved Task duration. The knowledge package becomes a-knowledge-v6 and fixed examples become planning-synthetic-v2. This round covers only A's rules and acceptance preparation; B/C integration is deferred.

M0 still needs decisions on shifts and return-to-depot policy, task deadlines, real engineering mappings and duration evidence, real-world threshold calibration, objective weights and GA parameters. The NUS-ISS building reference coordinate is fixed; B must verify the actual vehicle entrance when integrating road travel. The confirmed automatic-acceptance threshold is `0.60`, read centrally from confidence_threshold in demo_rules.example.json and frozen in auto_acceptance. It is not a calibrated probability of correctness. Do not treat a fixed shift as confirmed or silently replace depot coordinates. Explicitly label any placeholder as a demo assumption and configure it centrally; formal validation must not mix unconfirmed assumptions.

Step 5's [demo_rules.example.json](SystemCode/config/demo_rules.example.json) centralizes the demo threshold, eight-class mapping and single-candidate selection policy; see [demo detection and rules](Miscellaneous/DEMO_DETECTION_AND_RULES.md). Every output explicitly identifies demonstration data. `ready_for_task` means only that candidate calculation is complete, not that an inspection is accepted or a task is queued. Update the version when rule parameters change; do not promote these demo assumptions to formally approved values.

Step 6's [inspection/review/task workflow](Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md) generates detections from an explicitly selected demo case, retaining raw evidence, the complete rule snapshot and separate review/task histories. Road type is currently declared by the caller with its source recorded; do not claim that road eligibility has been automatically verified. Review and label corrections use the inspection's frozen rules. Task changes increment input_revision in the same transaction, and retries do not create duplicate tasks. HTTP inspection records were extended to a-workflow-v2 with additional fields such as mode and model-weight hash; clients strictly using the old record schema must update. Real Detection.is_demo=false, while demonstration-business Inspection/Task.is_demo=true. Real uploads follow single-primary-auto-v1: a primary box meeting the raw confidence threshold automatically creates a Task; lower confidence awaits review. Task severity, duration and priority still use demo mappings.

Step 7's [B/C handoff](Miscellaneous/BC_HANDOFF.md) freezes a-task-query-v1. TaskQueryService reads all active tasks and input_revision in one transaction and can join a caller's existing shared transaction; B must not combine paginated results from different revisions. Fixed 10/15/20-task points pass polygon validation only, without road verification. C uses a versioned knowledge package with references, distinguishing project facts, demo assumptions and unresolved decisions. Knowledge checks are not expert approval; specific route facts still come from B's plans. Before saving a planning result, recheck the input revision in the write transaction.

Repair tasks are checked against the JE/JW polygon union, including boundaries and respecting road-type restrictions; the designated NUS-ISS depot is exempt from the task-area restriction. Driving routes may leave the task area, and travel from the depot to the first task must be counted. All four crews share the depot, GA/Greedy use the same geographic-data version, and the map viewport must include both task area and depot. Return-to-depot policy is unresolved; configuration `null` must not default to `false`.

The first design limits assistant changes to crew availability and replans active tasks from one common start time. Road-closure detours, live vehicle tracking, complex crew skills and other extensions are not automatically in scope. On 2026-10-18 the user explicitly authorized account permissions: inspectors upload and see only their own results; a crew account is permanently linked to one crew and handles its tasks; central dispatchers access review, task, planning and other pages. Enforce permissions in frontend and backend; see the [account-role specification](Miscellaneous/ACCOUNT_ROLES.md) for interfaces and account management.

## 4. Responsibilities and code boundaries

The shared backend exists at `SystemCode/backend/roadguard/`. Create the following business subdirectories gradually as assigned, preserving ownership.

| Owner | Main modules/paths | Integration requirement |
| --- | --- | --- |
| A: project initiator | `SystemCode/model/`; backend `vision/`, `rules/`, `inspections/`, `tasks/` | Supplies detection, rules, review, tasks and examples; owns vision/rule evaluation |
| A: shared foundation | Backend entry point, configuration, database connection, shared errors/schemas, route registration, initialization/migration entry point | B/C supply required increments; A coordinates integration, avoiding separate backends or databases |
| B | Backend `crews/`, `routing/` | Supplies four-crew management, travel matrix, Greedy/GA, recalculation, plan storage, shared metrics and experiments |
| C | `SystemCode/frontend/`; backend `assistant/` | Supplies pages, map, GPT/RAG and change-confirmation workflow; calls A/B business services |
| A + C | `SystemCode/backend/knowledge/` | A owns business-knowledge correctness; C owns retrieval, indexing, citations and answers |
| Each owner; A compiles | Module tests, experiments, report chapters, installation instructions and video materials | Owners fix their modules; coordination by A does not mean writing every module or test |

- Proceed independently on internal changes that do not affect external behavior.
- For changes to shared schemas, database entry points, dependency lists, interfaces or another member's module, explain the reason, caller effects and required increments, and update affected contracts/documentation. Do not seek repeated authorization when the task already explicitly includes the change; PRs do not require another member's manual review.
- If blocked by upstream progress, develop with agreed, clearly labeled mock responses/fixed data; do not copy another module's business logic.
- Do not directly update business tables owned by another module: B obtains tasks through A's query service; C reads facts or executes changes through A/B services.
- Every member supplies their own tests, documentation and report material, not just an isolated script or a notebook that requires chat history to run.

## 5. Architecture, interface and data conventions

- Retain the course's four top-level directories: `SystemCode/`, `ProjectReport/`, `Video/`, `Miscellaneous/`; retain the root README's seven course sections.
- Use one FastAPI backend, one React frontend and shared SQLite connection/configuration. Routes handle input/output, services handle business logic and data access handles persistence; keep complex algorithms out of routes and UI.
- All APIs use `/api/v1`. See the [API contract](Miscellaneous/API_CONTRACT.md) for frozen parts and allocation section 7 for planned business paths. Define minimum request, success/error responses and examples before implementing a new interface; do not invent separate compatibility layers. Fixed JSON examples are development artifacts, not live business endpoints.
- IDs are strings; JSON fields use `snake_case`; coordinates are `latitude` and `longitude` in WGS84 decimal degrees; confidence is 0–1.
- Travel and repair durations use minutes. Timestamps are timezone-aware ISO 8601, stored/transmitted in UTC and displayed in `Asia/Singapore`. Algorithm runtime uses explicitly named second/millisecond fields and must not be confused with operational durations.
- Detections retain stable `detection_id`; `bbox_xyxy` uses original-image pixel coordinates with image dimensions, model version and `is_demo`. The frontend must not guess class or severity.
- Distinguish `null`, empty lists and zero: unknown repair duration is not zero; no plan is not a valid empty plan; unreachable travel is not zero minutes.
- Error responses contain at least `code`, `message` and optional `details`; the contract defines shared error codes and HTTP statuses. The frontend must not infer business state by matching natural-language errors.
- Update schemas, examples, caller-impact notes and necessary checks in the same PR as interface changes. Coordinate breaking changes with callers; do not silently rename, change units or remove fields.
- Once the backend generates OpenAPI, keep it consistent with the approved contract. Share the frontend API client and types rather than hand-writing different structures on each page.

## 6. Required business behavior

| Stage | Behavior that must be preserved |
| --- | --- |
| Detection/review | Unconfirmed low-confidence results cannot enter active tasks; no detection creates no task; repeated confirmation creates no duplicate |
| Rules | Priority, severity and duration come from A's rules; review corrections still pass through rule calculation; record rule version and reasons |
| Task status | Completed/cancelled tasks retain history but do not enter new plans; backend validates status and editable fields |
| Four-crew output | Unavailable crews receive no tasks; idle/unavailable crews remain identifiable; each assigned task appears once |
| Unassigned tasks | Explicitly return tasks and reasons; never discard tasks to improve metrics |
| Recalculation consistency | Task/crew changes update the input revision; a plan uses a consistent snapshot; stale results cannot overwrite the current plan |
| Failure feedback | Business data remains accessible after recalculation failure; mark the old plan stale; do not present old/mock results as new real results |
| Assistant | Answer using the specified plan's facts and reviewed knowledge with sources; explain insufficient evidence instead of inventing tasks, metrics or rules |
| Assistant changes | Structured preview first, user confirmation next, execution through B's service; repeated confirmation cannot repeat changes and stale requests cannot execute directly |
| Map | Stop order matches the plan; straight lines are labeled schematic; distinguish Google travel times from mock matrices |

These are acceptance constraints for future implementation. Each owner designs transaction boundaries, concurrency and storage against frozen contracts; they do not justify adding complex infrastructure prematurely.

## 7. Coding and environment conventions

- Use English for identifiers, repository text, UI, documentation and comments; names should convey business meaning. Conversation may follow the user's language. Python uses `snake_case` and `PascalCase` classes; React components use `PascalCase`, frontend functions/variables use `camelCase`, and API fields retain contract formatting.
- Use four-space Python indentation and two-space frontend indentation. Text is UTF-8 with LF under `.gitattributes`; follow established formatter configuration rather than introducing unrelated personal-style differences.
- Public services/interfaces need clear types and validation. Comment non-obvious algorithm constraints, rule evidence and exceptional behavior. Avoid duplicated business logic, oversized functions and swallowed exceptions that fabricate success.
- Minimize the change scope; do not also reformat the repository, refactor other modules, upgrade all dependencies or change the stack.
- A coordinates Python, Node, package-manager and dependency versions when establishing the foundation and records them in module READMEs/dependency files. Other members use the same versions and installation method.
- Maintain one agreed dependency/lock approach per environment; do not add conflicting npm, pnpm and Yarn lockfiles. Explain necessary new dependencies and update the relevant records.
- Use repository-relative or configurable paths, never hardcoded personal drive letters, usernames, secrets or model locations. Configuration examples must explain required fields.
- See the [backend guide](SystemCode/backend/README.md) for startup/dependency commands and [GitHub workflow/CI guide](Miscellaneous/GITHUB_WORKFLOW.md) for checks. Connect each new behavior to real tests. CI uses Python 3.11, Node 22 and npm; update CI, dependencies and development instructions together when changing this baseline.

## 8. Data, models, external services and experiments

- Follow `.gitignore`. The user-designated root `Dataset/` stores downloaded data, training/recovery weights, caches and run evidence, and is entirely excluded from GitHub. Do not commit secrets, actual `.env`, runtime databases, uploaded images, virtual environments, `node_modules`, large datasets or weights without separate authorization. The one deployment weight specified below is an explicit exception. Supply sanitized `.env.example` or other examples as needed.
- Each member configures external API keys locally as documented. Restrict browser-visible map credentials by use; never include backend secrets in frontend source or builds.
- Explicitly label mock/demo data; never silently substitute it when a service fails. Integrate fixed examples first, then verify the real model, Google data and GPT separately.
- The [dataset audit](Miscellaneous/DATASET_AND_LABEL_AUDIT.md) records the RDD2022ES source, labels 0–7 and this round's directory/sample checks; do not mix in the original RDD2022 four-class IDs. Original images and `xmirror_`/other related augmentations must not cross train/validation/test splits; do not select thresholds on test data. Do not claim images originate from Jurong without evidence.
- Address documented missing images/annotations and finish full content validation/class counts before preparing splits. Directory statistics or targeted samples are not proof of full-dataset quality. Preserve both the publisher's conflicting BY-SA body and BY-NC-SA metadata statements. Dataset labels do not directly establish priorities, repair times or engineering measurement thresholds.
- On 2026-10-13, the user explicitly authorized publishing the current best deployment weight as a Release attachment in this private repository. The Release remains a backup download channel; original Dataset content and training recovery checkpoints remain prohibited.
- On 2026-10-14, the user additionally authorized committing `SystemCode/backend/roadguard/model/roadguard-yolo11s-single-v1.pt` directly to this private repository so normal clone/pull provides it to members. The backend default manifest loads that location and checks its hash. After installing vision dependencies it starts without a separate download or installer. CI permits only this path, 19,218,837 bytes and SHA-256 `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`, also checking the manifest. All other weights and all Dataset files remain prohibited in Git. Model updates require the approved file, manifest and CI values to change together. Training code stays in `SystemCode/model/`; checkpoints and raw data stay in `Dataset/`. See the [deployment directory guide](SystemCode/backend/roadguard/model/README.md).
- Document acquisition location, version, checksum and reproduction steps for weights/large resources. Commit only necessary small examples that may be shared.
- GA/Greedy comparisons must use identical tasks, matrices, constraints and metric definitions. Run GA with multiple seeds and retain parameters, raw results, environment and code revision, including failed/infeasible results.
- Distinguish algorithm runtime, external API waits, travel time and repair completion time. Do not invent lateness without deadlines or claim real monetary savings without a cost model.
- Never fabricate accuracy, optimization gains, passing tests, completed training, user feedback or course coverage. Report figures must trace to saved experimental records.
- Explain the run size before large-scale training or significant external-service use. Stay within human-authorized scope/budget and do not retry without limit.

## 9. Git and collaboration workflow

1. Use a short-lived branch for one clear task, such as `feature/a-inspection-api`, `feature/b-ga-planner` or `feature/c-route-map`; documentation may use `docs/project-guidelines`. Start from synchronized `main` with known status and preserve uncommitted work.
2. Keep each commit focused. Suggested formats: `feat(routing): ...`, `fix(vision): ...`, `docs(team): ...`, `test(assistant): ...`. Commit text is English. Do not include others' unfinished work.
3. Open a PR before merging into `main`. PR titles, bodies, summaries, comments and merge descriptions are English; describe the problem/result, modules, interface/dependency changes, actual verification and limitations. Repository business documentation is English; member conversation may follow the user's language. Mark unfinished work as draft.
4. Under the initiator's explicit 2026-10-12 authorization, PRs require no manual review/approval. Ordinary ready PRs automatically Squash merge after checks pass. The submitter/agent first completes self-review, interface-impact notes and applicable verification; module owners fix their issues. Creating a non-draft PR enters this automatic process without asking again whether to merge.
5. [RoadGuard Auto Merge](.github/workflows/auto-merge.yml) merges only PRs submitted by members with repository write access. It checks latest CI success for the latest commit, inclusion of current `main`, no conflicts, English title/body and no unresolved changes requested. Drafts, forks, stale/failed checks or branches behind `main` wait until fixed/synchronized and pushed to trigger checks.
6. Changes to files within `.github/`, including moves in/out, affect checks and merge control, so the bot does not merge its own rules. For such PRs, the agent checks the diff/latest CI and merges under the initiator's existing authorization, without human review or repeated confirmation. Do not bypass this boundary using an ordinary business PR.
7. Ordinary CI is read-only. Merge workflows execute only trusted scripts from `main`, never PR code or PR artifacts. The bot explicitly triggers `main` CI after merging; failures are addressed through fix PRs, without automatic rollback. The current plan cannot enforce a ban on direct pushes/manual bypasses, but members must still follow this workflow. See [GitHub collaboration](Miscellaneous/GITHUB_WORKFLOW.md) for detailed conditions/costs.

For local-only delivery, do not automatically push or create a PR. A PR explicitly requested only for review and not yet for merge must be draft. When committing, synchronization or a ready PR is requested, follow the automatic-merge agreement above. Do not force push, delete members' branches, rewrite shared history, discard others' work or recreate a database containing data without authorization. Resolve conflicts by business meaning rather than replacing entire files.

Record each task's owner, objective, acceptance conditions and dependencies, optionally in a GitHub Issue. Write critical cross-member decisions into repository documents/Issues/PRs rather than leaving them only in private chat.

## 10. Verification and completion criteria

Run necessary, meaningful checks for affected behavior. A bug fix needs verification capable of detecting it; documentation-only changes do not justify installing the entire application or creating unrelated tests.

| Module | Key cases to cover |
| --- | --- |
| A: vision/rules/tasks | No detection, low confidence, review correction/dismissal, repeated confirmation, invalid coordinates/input, task completion/cancellation, rule boundaries |
| B: routing | No tasks, one task, fewer tasks than four crews, one/all crews unavailable, unreachable/infeasible inputs, no missing/duplicate tasks, fixed seeds, stale results |
| C: pages/assistant | Loading/empty/failure states, four crews and order, mock-source labeling, supported/unsupported answers, no change before confirmation, cancellation/staleness/repeated confirmation |
| Integration | Upload → review/accept → task → planning → display; recalculation and failure feedback after task/crew changes |

Before delivery:

- [ ] Work stays within authorization, conforms to agreed behavior and preserves module boundaries/others' changes.
- [ ] Interfaces, examples, configuration and startup/usage documentation are updated together.
- [ ] Report actual check commands/results; explain checks not run and do not call unverified behavior passed.
- [ ] Distinguish real/mock data and implemented/planned functionality.
- [ ] No secrets, unrelated artifacts, training-data leakage or fabricated results.
- [ ] Explain remaining dependencies, integration owners, limitations and whether delivery is local/committed/pushed/merged.

## 11. Agent handoff

At task completion, briefly state:

1. What was completed and which problem it solves.
2. Changed files and A/B/C interface/configuration effects.
3. Actual verification/results and what remains unverified.
4. Missing work and the next member's integration needs.
5. Git delivery status, including commit/PR identifiers when applicable.

When keys, models or upstream interfaces are missing, deliver reviewable local work and explicit limitations without claiming end-to-end completion. Synchronize this file and affected documents when rules change rather than creating contradictory personal versions. Tool-specific agent configurations should reference this file and add only tool-specific instructions.

## 12. Agent kickoff prompt for members

After opening the repository root on their computer, members can send this prompt to their agent, replacing the role and task:

```text
This is the RoadGuard three-person collaboration repository. I represent [A / B / C].
First read root AGENTS.md, Miscellaneous/PROJECT_SCOPE.md,
Miscellaneous/TEAM_WORK_ALLOCATION.md and my module README.
This task is: [specific objective and acceptance criteria].
This is planning only; write business code only when I explicitly request implementation.
Before starting, briefly state the rules read, owned modules, intended changes,
interface dependencies and verification method.
Follow shared contracts and preserve others' changes. At completion, state file changes,
actual verification, outstanding integration and local/commit/push status.
Do not expand this task's scope.
```

For implementation, replace the planning-only sentence with: “Implementation of the task above and necessary verification are authorized.”

Codex supports reading `AGENTS.md` in a project. For agents that do not read it automatically, explicitly provide this file and ask them to summarize applicable rules first. Reread it or start a new session after pulling rule updates. Shared files standardize project conventions but do not guarantee identical outputs from different tools/models; self-review and applicable automated verification are still required. [Official OpenAI guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
