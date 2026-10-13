# Installation and user guide - persisted workflow and optional real vision

The backend is runnable using the [backend guide](../SystemCode/backend/README.md). Start it from the repository root, then open `/docs` and `GET /api/v1/health`. Startup loads the scenario and migrates the shared database, including inspection/task tables. No model, API key or paid external service is required for this demo workflow.

The [initial API contract](../Miscellaneous/API_CONTRACT.md) and [fixed JSON examples](../SystemCode/contracts/README.md) support development by B/C. Examples are synthetic, are not image inference results, and are not loaded into runtime tables. A healthy backend does not mean the detector, planner or assistant is ready.

For the implemented step 5 workflow, use the [demo detection and rule guide](../Miscellaneous/DEMO_DETECTION_AND_RULES.md): select one of seven fixed scenarios and request its assessment through `/api/v1/demo/assessments`. Responses show the demo source, review decision, candidate, rule version and reasoning. They do not persist inspections/tasks or update planning input revisions.

Step 6 is implemented: follow the [inspection/review/task guide](../Miscellaneous/INSPECTION_REVIEW_TASK_WORKFLOW.md) for multipart upload, explicit demo selection, review, task modification, retries and persistence. Use a local development server; this step adds no authentication or public deployment. Back up the database and upload directory together. Road type is caller-declared, and stored image coordinates do not establish a real capture location. Four-crew routes, frontend and assistant instructions remain pending.

Step 7 provides a [B/C handoff guide](../Miscellaneous/BC_HANDOFF.md): `GET /api/v1/tasks/snapshot`, the internal shared-transaction query service, fixed 10/15/20-task inputs, versioned knowledge, and a runnable HTTP example with response export. The example creates demo records and should run against its documented isolated development database. Source-checked knowledge does not imply a working GPT/RAG service or expert approval.

Step 8 adds optional local eight-class pixel inference. Follow the [training/recovery guide](../SystemCode/model/TRAINING.md) and [real vision API guide](../Miscellaneous/REAL_VISION_API.md). Set `ROADGUARD_VISION_MANIFEST_PATH` in the server environment (or PyCharm run configuration) to `Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/model_manifest.json` on the training computer, then restart the backend. Upload `mode:"real"` without a scenario ID. Every nonempty real result requires review; repair rules and task geography remain simulated. The detector is disabled unless explicitly configured. Other computers need the local artifacts separately because the whole `Dataset/` directory is excluded from GitHub.

The [step 8 acceptance record](../Miscellaneous/STEP8_VISION_ACCEPTANCE.md) reports actual GPU training, interruption/resumption, held-out metrics, isolated HTTP verification and cache cleanup. This is an experimental 10-epoch baseline; it does not establish a calibrated acceptance threshold or production accuracy. The API record contract is now a-workflow-v2; the task snapshot stays a-task-query-v1.

The final application guide must consolidate and verify the following as remaining components are implemented:

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
