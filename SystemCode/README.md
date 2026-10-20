# System code

This directory contains the implemented RoadGuard local prototype. Its name follows the course submission template; the template's historical CLIPS/Python 2 example is not an application dependency.

| Directory | Current responsibility |
| --- | --- |
| `backend/` | One FastAPI/SQLite application: authentication, vision, rules, inspections, tasks, crews and Greedy/GA planning |
| `frontend/` | React inspector, dispatcher and fixed-crew workspaces; schematic map and algorithm comparison |
| `model/` | RDD2022ES preparation, recoverable YOLO training, evaluation and deployment manifest |
| `experiments/` | Reproducible vision/routing experiments and saved results |
| `tests/` | Module, API and integration checks |
| `config/` | Scenario, demonstration business rules and routing assumptions |
| `contracts/` | Shared DTO schemas and explicitly synthetic integration fixtures |

The implemented workflow is image upload → primary detection → automatic acceptance at raw confidence >=0.60 or human review → one rule-based task → explicit four-crew planning → crew completion. No detection creates no task. Rule snapshots, history, idempotency and input revisions preserve consistency. Task/crew changes mark existing plans stale; they do not automatically recalculate.

The [backend guide](backend/README.md), [frontend guide](frontend/README.md) and [installation/user guide](../ProjectReport/INSTALLATION_AND_USER_GUIDE.md) cover startup and account provisioning. Use Python 3.12 for the complete vision environment and Node 22.x >=22.12 with npm >=10. Base CI uses Python 3.11 without the optional vision dependencies. The approved deployment weight is included in the repository; inference does not require downloading Dataset.

The [geographic baseline](../Miscellaneous/JURONG_SCOPE_AND_DEPOT.md) defines the Jurong East/West task boundary and shared NUS-ISS simulated origin. Polygon validation is implemented; road eligibility is caller-declared. The routing configuration uses a simulated matrix by default, optional Google Routes estimates, and demonstration shift/return policies. The displayed map is schematic, not road navigation.

The [integration record](../Miscellaneous/INTEGRATION_ACCEPTANCE_20261018.md) and [frontend acceptance notes](frontend/DESIGN_PREVIEW.md) document the local workflow and later account/mobile checks. Historical Step 5–8 documents describe those earlier deliveries. The [a-knowledge-v10 corpus](backend/knowledge/README.md) contains eleven citable documents covering scope/rules, GA/Greedy, saved plans, accounts, operations, recorded evaluations and the proposed RAG integration contract, with 30 synthetic acceptance specifications. GPT/RAG retrieval, answers and confirmed changes remain unimplemented. Model accuracy and independent local validation remain separate from software acceptance.
