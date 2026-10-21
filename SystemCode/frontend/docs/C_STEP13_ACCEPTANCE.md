# C step 13: historical local integration acceptance

Date: 2026-10-21. Owner: C. Original branch: feature/c-knowledge-retrieval. This English translation preserves the historical acceptance scope; these results are not verification of subsequent changes. Local acceptance without paid services completed. Real model and external-provider acceptance remained pending. Steps 10–13 were uncommitted at the time of recording.

This round added acceptance tests, evidence and status documentation. It did not change A/B business rules or routing algorithms. Existing workspace changes were preserved. Earlier "not implemented" statements are historical baselines; the assistant modules describe steps 10–12.

## Recorded checks

| Layer | Historical result and scope |
| --- | --- |
| Backend regression | 1,100 passed, 1 skipped, about 70 seconds. Local Python 3.12; CI baseline remained Python 3.11. |
| Step 13 cases | 22 passed: 10 dynamic route questions, 11 adjustment cases and one cross-role HTTP workflow. Repeated successfully after adding recovery through a new application instance. |
| Frontend | 166 passed, lint, TypeScript and Vite build passed on Node 22.23.3. |
| Browser | Codex browser connected to isolated FastAPI/SQLite: low-confidence upload, review, two-algorithm planning/comparison, crew completion, stale routes and recalculation excluding completed tasks. |
| Mock/mobile | Explicit mock failure displayed errors and blocked writes. Live source recovery worked. Routes and expanded assistant at 390×844 had document width 390 without page overflow. |

Test source: `SystemCode/tests/test_c_acceptance.py`. [Per-case evidence and versions](../../experiments/assistant/c-step13-20261021/README.md). Existing regression covered authentication/CSRF, confidence gate, image/location validation, review corrections/rejection, tasks/routes, corrupted knowledge, model doubles/injection, preview expiry, concurrency, rollback and recovery.

## Recorded browser workflow

1. Inspector uploaded a synthetic PNG marked `C13 SYNTHETIC TEST`, explicitly choosing low_confidence. The fixed mock pothole confidence was 42%; review was pending, no active task existed, revision 0.
2. Dispatcher confirmed review, creating a P2 / 120-minute / demo-rules-v2 task at revision 1. No automatic recalculation occurred.
3. Explicit recalculation assigned one task and left none unassigned in both GA and Greedy. Crew-01 was assigned; three idle crews remained visible. The map declared schematic order and simulated_haversine_v1 travel.
4. Same-run comparison confirmed consistent plans. Repair minutes and algorithm milliseconds were separate. Delay without deadlines was unavailable. A single run was not evidence of general GA superiority.
5. Crew-01 account showed only its workspace. Two explicit actions completed its task, showing 1/1 complete, retained history and stale saved route.
6. Dispatcher active queue became empty at revision 2. Old map was stale. Recalculation produced zero tasks for both algorithms, retaining all four idle crews.
7. Explicit mock failure showed an error and blocked writes; live source recovery succeeded. Narrow-screen menu, routes and assistant were accessible. Unconfigured model status was clear and disabled question submission.

Inspection ID: `07b03f3e3ff34d3d86e0878d85783106`. Task ID: `368d51e024554cdcadcd9a64cc858355`. Initial GA: `plan-caa3061b80624d4b8af668a23bf4349c`; Greedy: `plan-12173c567cdc4d718946b14ea4f77960`. After completion GA: `plan-a52b8ab590bd4d458a2e0e7e3564a19c`; Greedy: `plan-658b64a9c2b34cee83bbe7621b542ae9`. These are isolated acceptance records, not real maintenance tasks.

The step 12 assistant record covers preview, review, confirmation, saved status after failure, explicit recovery, refresh and cancellation. Independent HTTP cases rechecked changes and role transitions in this round.

## Reproduction

Use the backend dependency environment from the repository root. Default tests create temporary databases and images without reading the development database.

```sh
python -m pytest SystemCode/tests/test_c_acceptance.py -q
python -m pytest SystemCode/tests -q
cd SystemCode/frontend
npm run lint
npm run test:ci
npm run build
```

For per-case evidence choose a new directory. Only cases with all assertions passed receive passed=true. Use the pytest exit status, not old output files, to assess a new run.

```sh
ROADGUARD_ACCEPTANCE_OUTPUT=/tmp/roadguard-c13-new-run python -m pytest SystemCode/tests/test_c_acceptance.py -q
python .github/scripts/check_repository.py
python SystemCode/frontend/scripts/export_contract.py --check
```

Tests block real model network access and use simulated travel. Passwords are isolated fixtures. For demonstrations use a new isolated DB/upload directory and provision inspector, dispatcher and four bound crew accounts according to ACCOUNT_ROLES.md. Never use the normal development database as disposable test data. The seven browser steps need no API key.

## Limits and findings

| Item | Historical conclusion |
| --- | --- |
| Acceptance script correction | Initially attempted to read detection_id from the simplified upload response; corrected to read inspection detail, then passed. This was a test defect. |
| Product paths | No blocking defect found in tested paths; this does not establish all-device, concurrency or production correctness. |
| Model quality | Ten questions used fixed evidence-selection doubles: eight evidence answers, one insufficient answer and one stale response. This is interface coverage, not 100% GPT accuracy. |
| GPT/Google | No paid model or real Google calls. Connectivity and real quality remained pending configuration and authorization. |
| YOLO | Acceptance environment lacked torch/ultralytics and used explicit mock detection. Browser results do not establish inference accuracy. |
| Recovery | A new app instance read saved receipts. Exception/time-advance tests covered interruption leases and superseded attempts; no power-loss or forced-process stress test. |
| Map/data | Schematic stop order and synthetic coordinates/images/travel do not establish road access or model quality. |
| Engineering | Main JS bundle >500 kB and Starlette/httpx deprecation warnings remained; dependency upgrades and splitting were separate work. |
| Devices | Codex browser and 390px viewport only; no Safari, physical Android/iOS or full assistive-technology audit. |

Step 14 remained responsible for formal guides, report chapters, screenshots and recordings. Team members still needed to record their own explanation. This test document is not the final course video or proof of complete group acceptance.
