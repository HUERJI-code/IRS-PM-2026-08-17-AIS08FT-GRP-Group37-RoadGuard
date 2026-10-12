# Installation and user guide - demo assessment delivery

The shared backend is runnable using the [backend guide](../SystemCode/backend/README.md). Start it from the repository root, then open `/docs` and `GET /api/v1/health`. Startup loads the scenario and initializes only the shared infrastructure database. No model, API key or paid external service is required for this foundation.

The [initial API contract](../Miscellaneous/API_CONTRACT.md) and [fixed JSON examples](../SystemCode/contracts/README.md) support development by B/C. Examples are synthetic, are not image inference results, and are not loaded into runtime tables. A healthy backend does not mean the detector, planner or assistant is ready.

For the implemented step 5 workflow, use the [demo detection and rule guide](../Miscellaneous/DEMO_DETECTION_AND_RULES.md): select one of seven fixed scenarios and request its assessment through `/api/v1/demo/assessments`. Responses show the demo source, review decision, candidate, rule version and reasoning. They do not persist inspections/tasks or update planning input revisions.

The complete application guide remains to be written and verified as these capabilities are implemented:

1. Supported operating system and tested Python/Node versions.
2. Dependency installation from the committed dependency files.
3. Local environment configuration and optional external-service setup.
4. Database initialization and four-crew scenario loading.
5. Backend and frontend startup commands.
6. Image submission, uncertainty review and task management.
7. Viewing four crew routes and comparing GA with greedy.
8. Route explanation and supported changes, when implemented.
9. Troubleshooting, demonstration mode and limitations.
10. Reproducing tests and experiments.

Use the paths under `SystemCode/` in the final commands. Include screenshots from the actual implementation.
