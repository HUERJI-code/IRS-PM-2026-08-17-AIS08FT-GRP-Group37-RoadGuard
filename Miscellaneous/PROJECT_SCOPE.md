# RoadGuard scope addendum

Recorded: 2026-10-10. This records the current project decision, not the date of the teacher's feedback.

## Confirmed changes

- Default repair crews: **four**, replacing the proposal's two-crew scenario.
- Demonstration area: **Jurong, Singapore**.
- This delivery: a course-template repository scaffold for review before implementation.
- Repository: private GitHub repository under the project owner's account.
- Course start date: 2026-08-17. Batch code: AIS08FT. Repository team label: Group7.
- The previous prototype is abandoned; implementation starts from this scaffold.

## Working scenario

One fictional maintenance department coordinates four simulated crews from one shared fictional depot. The system will accept single images, identify damage and basic severity, apply priority rules, maintain an accepted-task queue and calculate an ordered route for each crew. Uncertain detections require review.

The planned stack follows the proposal: React frontend, Python backend, SQLite, YOLO/RDD2022ES, Google travel-time data, a group-built GA, a greedy baseline and GPT/RAG route explanations.

Routing tasks are synthetic test data located inside the study area once its boundary is specified. The image dataset is not claimed to originate from Jurong.

## Design decisions still needed

- The exact Jurong study boundary; do not assume the name alone defines a machine-checkable polygon.
- Fictional depot coordinates within that boundary.
- Shift length, repair/service times and crew capability assumptions.
- The definition of urgent-task lateness and the associated weights.
- GA encoding, population, stopping criteria and reproducible seeds.
- Routing-provider behavior and the distinction between road-network and simulated travel times.

## Evaluation implications

Four crews can reduce operational completion time without reducing algorithm runtime. Geographic restriction reduces optimization size only when it reduces the task set or supports an explicit decomposition. Report those effects separately.

Use four crews for the primary 10/15/20-task evaluation. Any optional two/three/four-crew sensitivity experiment must keep tasks, travel times and constraints comparable.

## Development boundary

The project owner requested deletion of the earlier `RoadGuard` prototype. Do not migrate its code or historical experimental results into this baseline. The original course materials, proposal and presentation remain historical references in the parent workspace.
