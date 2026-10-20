# RoadGuard scope addendum

Recorded: 2026-10-10. This records the current project decision, not the date of the teacher's feedback.

Updated: 2026-10-20. The geographic baseline and user-selected dispatch origin are defined in [Jurong scope and NUS-ISS depot](JURONG_SCOPE_AND_DEPOT.md).

## Confirmed changes

- On 2026-10-14 the owner finalized course-simulation rule durations: P3=60, P2=120 and P1=240 minutes per task, retaining the eight severity/priority mappings and 0.60 automatic gate. Runtime version is demo-rules-v2; these are simulated service times, not measured engineering standards or deadlines. See [business baseline](BUSINESS_RULES_BASELINE.md) and [acceptance checklist](INTEGRATION_ACCEPTANCE_CHECKLIST.md). The later [18 October integration record](INTEGRATION_ACCEPTANCE_20261018.md) covers the implemented frontend and planning workflow.

- Typical capture scenario (2026-10-13): one main damage type and one main subject per photo. This is not a guarantee that every input contains damage or exactly one object. The [single-main-damage experiment](SINGLE_DAMAGE_OPTIMIZATION.md) retains raw detections and review; The [released model integration](MODEL_RELEASE_AND_BACKEND.md) now provides a default local manifest and persisted primary suggestion; model-quality acceptance remains pending. The later user-approved a-workflow-v5 returns at most one box and automatically creates one task when its raw confidence is at least 0.60; raw evidence is retained internally. See [response fields](INSPECTION_RESPONSE_FIELDS.md).

- Default repair crews: **four**, replacing the proposal's two-crew scenario.
- Task service area: **Jurong East and Jurong West, Singapore**, using the frozen URA Master Plan 2025 polygons (approximately 32.55 km²).
- Shared simulated dispatch origin: **NUS-ISS**, 25 Heng Mui Keng Terrace, Singapore 119615; latitude `1.292149`, longitude `103.776551`. This specified depot is allowed outside the task service area; travel from it to the first task must be counted.
- Current delivery: initial contracts, shared backend, stateless demo previews, persisted inspection/review/task workflows, and the [B/C handoff](BC_HANDOFF.md) with consistent task snapshots, fixed synthetic inputs and versioned source-checked knowledge. Polygon validation is implemented; road type is explicitly user-declared. Rule parameters remain demo assumptions; opt-in real image inference is implemented with a user-selected primary-confidence gate (default 0.60) and review below it. See [Step 8 acceptance](STEP8_VISION_ACCEPTANCE.md) for actual training evidence. Four-crew Greedy/GA planning, optional Google travel matrices, the authenticated React frontend and fixed-crew completion are implemented. Task/crew changes mark plans stale; recalculation is explicit. The map is schematic, and knowledge retrieval/generation remains unimplemented.
- Repository: private GitHub repository under the project owner's account.
- Course start date: 2026-08-17. Batch code: AIS08FT. Repository team label: Group7.
- The previous prototype is abandoned; implementation starts from this scaffold.

## Working scenario

One fictional maintenance department coordinates four simulated crews from one shared simulated depot at the real NUS-ISS location. This does not describe an actual NUS-ISS maintenance operation. The system accepts single images, predicts a primary damage label and box, applies demonstration severity/priority rules, maintains accepted tasks and explicitly calculates ordered crew routes. Uncertain detections require review.

The implemented stack uses React, one Python/FastAPI backend, SQLite, YOLO/RDD2022ES, a group-built GA and a Greedy baseline. Travel matrices are simulated by default, with optional Google Routes estimates. GPT/RAG route explanations remain proposed.

The [dataset and label audit](DATASET_AND_LABEL_AUDIT.md) pins Juuso's RDD2022ES version 1 and verifies its eight source labels. Full content validation and grouped splits are now recorded by the Step 8 pipeline; the original audit remains the source-history record. Dataset severity qualifiers do not define project priorities or repair durations, and the publisher's license statements conflict as documented in the audit.

Routing experiments use synthetic task coordinates validated against the frozen study boundary, including polygon edges; their declared road eligibility is not independent road verification. Expressway mainline/ramp repair tasks and private or restricted internal-road tasks are excluded. Detailed road exclusions are in the geographic baseline. Routes may travel outside the task area, including the journey from NUS-ISS. The image dataset is not claimed to originate from Jurong.

## Design decisions still needed

- Verify the actual drivable NUS-ISS access point before operational use. Recorded Google estimates do not independently verify vehicle access to the configured building reference point.
- Decide whether crews must return to the depot. The origin-to-first-task journey is required under either policy.
- Shift length and crew capability assumptions; measured operational service times remain unvalidated, while the course-simulation durations are fixed above.
- The definition of urgent-task lateness and the associated weights.
- Validate the operational objective weights and service assumptions; algorithm implementation does not establish engineering suitability.

The [routing configuration](../SystemCode/config/routing.example.json) already defines GA encoding support, population/stopping parameters, seeds, provider behavior and demo scheduling assumptions (480 minutes and return to depot). Those are implemented demonstration choices; the shared project configuration still leaves the operational return policy unresolved. Google failure is explicit and does not silently switch to simulation.

## Evaluation implications

Four crews can reduce operational completion time without reducing algorithm runtime. Geographic restriction reduces optimization size only when it reduces the task set or supports an explicit decomposition. Report those effects separately.

Use four crews for the primary 10/15/20-task evaluation. Any optional two/three/four-crew sensitivity experiment must keep tasks, travel times and constraints comparable.

## Development boundary

The project owner requested deletion of the earlier `RoadGuard` prototype. Do not migrate its code or historical experimental results into this baseline. The original course materials, proposal and presentation remain historical references in the parent workspace.
