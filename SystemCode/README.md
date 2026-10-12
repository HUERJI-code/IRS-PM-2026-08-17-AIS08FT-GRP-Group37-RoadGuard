# System code

This directory contains the new RoadGuard implementation. Its name follows the course submission template; the template's historical CLIPS/Python 2 example is not an application dependency. The [shared backend](backend/README.md) and [initial contracts](contracts/README.md) are available; the remaining business modules are planned.

| Directory | Planned responsibility |
| --- | --- |
| `backend/` | Python API, confidence gate, business rules, task state, GA/greedy planning and route explanations |
| `frontend/` | React interface for inspections, review, tasks and four crew routes |
| `model/` | RDD2022ES preparation, YOLO training, evaluation and model integration |
| `experiments/` | Repeatable experiments and clearly identified measured results |
| `tests/` | Cross-component and end-to-end tests |
| `config/` | Shared scenario configuration |
| `contracts/` | Frozen DTO schemas and explicit demo fixtures for A/B/C integration |

`config/project.example.json` records the agreed scenario and is loaded by the backend at startup. Loading it does not create crew/task records or implement planning.

Implementation should use four crews by default and expose crew count as a parameter rather than hard-coding two routes. The [geographic baseline](../Miscellaneous/JURONG_SCOPE_AND_DEPOT.md) defines the JE/JW task boundary and the shared NUS-ISS origin outside it. Geographic validation remains unimplemented. Configuration file paths are relative to the repository root; the return-to-depot policy remains undecided.
