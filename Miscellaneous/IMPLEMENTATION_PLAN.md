# Implementation plan

All application milestones below are pending.

Step 1 geography is documented as of 2026-10-12: [Jurong East/West boundary and NUS-ISS simulated origin](JURONG_SCOPE_AND_DEPOT.md), with static GeoJSON and matching example configuration. Task contracts, business rules and routing constraints remain to be defined; this does not complete M0 or implement application behavior.

See [the three-person work allocation and interface draft](TEAM_WORK_ALLOCATION.md) for ownership: A (project owner) leads vision, rules, backend foundations and integration; B leads four-crew routing; C leads the frontend and assistant. These are planned responsibilities, not completed contributions.

| Step | Deliverable | Acceptance evidence |
| --- | --- | --- |
| 1 | Confirm study boundary, depot, task model and routing constraints | Written scenario and consistent configuration |
| 2 | Backend/frontend startup, database schema and four-crew configuration | Health endpoint and visible four-crew screen |
| 3 | Image upload, labelled demo detector, confidence gate and rules | Accepted and review-required cases with rule traces |
| 4 | Task queue, travel-time provider and greedy planner | Valid routes and explicit handling of unassigned tasks |
| 5 | Group-built GA and automatic replanning | Valid four-crew routes, deterministic seeded checks and queue-change demonstration |
| 6 | RDD2022ES training/evaluation and real detector integration | Held-out metrics and documented dataset splits |
| 7 | Proposed GPT/RAG explanation workflow | Grounded answers; confirmed changes routed through the backend planner |
| 8 | Comparative experiments and end-to-end validation | Reproducible results and documented limitations |
| 9 | Final report, user guide and two videos | Completed submission checklist |

Start implementation after the repository structure and current scope have been reviewed. Each milestone should add runnable behavior and its necessary checks rather than pre-populating success claims.
