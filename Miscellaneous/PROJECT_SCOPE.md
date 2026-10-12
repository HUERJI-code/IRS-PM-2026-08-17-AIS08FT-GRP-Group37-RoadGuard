# RoadGuard scope addendum

Recorded: 2026-10-10. This records the current project decision, not the date of the teacher's feedback.

Updated: 2026-10-12. The geographic baseline and user-selected dispatch origin are defined in [Jurong scope and NUS-ISS depot (中文)](JURONG_SCOPE_AND_DEPOT.md).

## Confirmed changes

- Default repair crews: **four**, replacing the proposal's two-crew scenario.
- Task service area: **Jurong East and Jurong West, Singapore**, using the frozen URA Master Plan 2025 polygons (approximately 32.55 km²).
- Shared simulated dispatch origin: **NUS-ISS**, 25 Heng Mui Keng Terrace, Singapore 119615; latitude `1.292149`, longitude `103.776551`. This specified depot is allowed outside the task service area; travel from it to the first task must be counted.
- This delivery: a course-template repository scaffold for review before implementation.
- Repository: private GitHub repository under the project owner's account.
- Course start date: 2026-08-17. Batch code: AIS08FT. Repository team label: Group7.
- The previous prototype is abandoned; implementation starts from this scaffold.

## Working scenario

One fictional maintenance department coordinates four simulated crews from one shared simulated depot at the real NUS-ISS location. This does not describe an actual NUS-ISS maintenance operation. The system will accept single images, identify damage and basic severity, apply priority rules, maintain an accepted-task queue and calculate an ordered route for each crew. Uncertain detections require review.

The planned stack follows the proposal: React frontend, Python backend, SQLite, YOLO/RDD2022ES, Google travel-time data, a group-built GA, a greedy baseline and GPT/RAG route explanations.

The [dataset and label audit](DATASET_AND_LABEL_AUDIT.md) pins Juuso's RDD2022ES version 1 and verifies its eight source labels. Full archive-directory inspection and targeted content sampling are complete; full training-data validation and splits remain pending. Dataset severity qualifiers do not define project priorities or repair durations, and the publisher's license statements conflict as documented in the audit.

Routing tasks are synthetic test data on eligible public motor roads inside the frozen study boundary, including polygon edges. Expressway mainline/ramp repair tasks and private or restricted internal-road tasks are excluded. Detailed road exclusions are in the geographic baseline. Routes may travel outside the task area, including the journey from NUS-ISS. The image dataset is not claimed to originate from Jurong.

## Design decisions still needed

- Verify a drivable NUS-ISS access point before obtaining the real travel matrix; the current coordinate is a building address point.
- Decide whether crews must return to the depot. The origin-to-first-task journey is required under either policy.
- Shift length, repair/service times and crew capability assumptions.
- The definition of urgent-task lateness and the associated weights.
- GA encoding, population, stopping criteria and reproducible seeds.
- Routing-provider behavior and the distinction between road-network and simulated travel times.

## Evaluation implications

Four crews can reduce operational completion time without reducing algorithm runtime. Geographic restriction reduces optimization size only when it reduces the task set or supports an explicit decomposition. Report those effects separately.

Use four crews for the primary 10/15/20-task evaluation. Any optional two/three/four-crew sensitivity experiment must keep tasks, travel times and constraints comparable.

## Development boundary

The project owner requested deletion of the earlier `RoadGuard` prototype. Do not migrate its code or historical experimental results into this baseline. The original course materials, proposal and presentation remain historical references in the parent workspace.
