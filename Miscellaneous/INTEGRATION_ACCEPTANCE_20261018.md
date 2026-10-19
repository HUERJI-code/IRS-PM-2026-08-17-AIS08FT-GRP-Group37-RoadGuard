# A/B/C frontend/backend integration acceptance record

Date: 2026-10-18; executed by coding agent for A; scope: pulled B scheduling/C frontend plus A's existing real model/business APIs. Conclusion: the current main workflow ran locally; fixed one upload error occurring only after real vision dependencies load. Assistant remains unimplemented; real Google travel was not accepted in this round. This is not complete-project acceptance.

## 1. Code and runtime isolation

- Baseline 4fa0c38 (`feat: implement frontend foundation`), confirmed equal to origin/main after fetching.
- Fix branch fix/integration-image-decoder; local at acceptance completion, then delivered by separate PR as requested. GitHub checks/merge follow that PR; later frontend improvements are excluded.
- Existing uncommitted YOLO context-crop work preserved; no training/deployment-weight change.
- Python 3.12.14, Node 22.23.3, npm 10.9.9; npm ci followed package-lock.json. This does not replace remote Python 3.11 CI.
- Frontend http://127.0.0.1:5173; isolated backend http://127.0.0.1:8001; Swagger http://127.0.0.1:8001/docs; unchanged /api proxy to 8001.
- SQLite Dataset/acceptance/integration-20261018/workflow.sqlite3; uploads/ alongside. Normal database/user's 8000 service untouched.
- Explicit ROADGUARD_TRAVEL_MATRIX_PROVIDER=simulated. Existing B demo parameters: four crews, NUS-ISS, 480-minute shift, return required. No promotion to real standards/new confirmed decisions.
- Committed roadguard-yolo11s-single-v1.pt, SHA-256 464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488; CPU inference, no training/download.

## 2. Actual browser acceptance

Live backend used. Except explicitly selected read-only failure fixtures for error-page testing, business actions called actual APIs against the isolated DB.

| Action | Result |
| --- | --- |
| Home/empty active list | App/DB connected, zero tasks; no-plan distinct from empty plan |
| Local image/real upload | Existing 05-pothole-asphalt.png uploaded; details show deployed model, one alligator_crack box at about 25.3%, pending review |
| Correct/accept | Corrected to pothole, P2/120-minute task; original label/confidence/review retained |
| One-task planning | Same-round GA/Greedy; four crews, one assigned/three idle; map includes Jurong/outside NUS-ISS |
| Disable Crew 01 | Saved change marks plan stale; explicit recalculation keeps unavailable crew visible and reassigns |
| Complete | Save completion; read-only record/history, removed active, input-change notice |
| 20-task map/comparison | All active tasks read; two saved plans, three stops each crew, eight unassigned with reasons; GA/Greedy switch |
| Same-round guard | Recalculation navigation confirms matching round; differing assigned sets suppress time/objective improvement rates; direct comparison lacks batch evidence |
| Explicit failure fixture | “Simulation · Service failure” shows structured error/removes unverified metrics; live mode restores reads. Controlled frontend failure, not real Google failure |
| Assistant | Explicit “business functionality not connected”; placeholder not counted passed |

Photo coordinate 1.3405,103.706 is synthetic Jurong, not capture evidence. Pothole misclassified as alligator cracking demonstrates remaining recognition problems. This validates integration/routing/human correction, **not Precision/Recall targets**.

## 3. Actual HTTP and automated checks

20 local HTTP acceptance groups passed, 201 requests through frontend 5173 proxy:

- Four-field upload/single-box details/high-confidence automatic tasks/inclusive 0.60 versus 0.5999/replay.
- Corrupt-image validation after real YOLO loaded; outside/invalid images rejected without task/revision changes.
- Low-confidence confirm/correct/dismiss; no detection/no task; stale review 409/retries without duplicate task/history.
- Label corrections recalculate 60/120/240-minute P3/P2/P1; invalid location atomic rejection; completion/cancellation retain history and leave snapshots.
- Crew disable/replay/stale plans/stale-input 409; all disabled gives no_available_crew per task.
- 0/1/10/15/20 tasks; four crews; each task exactly once assigned/unassigned; saved durations, depot/return counted, each crew ≤480 minutes.
- GA/Greedy identical revision/start/settings/mock matrix; online GA records Greedy seed, no worse on priority/objective scoring.

| Tasks | Greedy assigned/unassigned | GA assigned/unassigned |
| --- | --- | --- |
| 0 | 0 / 0 | 0 / 0 |
| 1 | 1 / 0 | 1 / 0 |
| 10 | 10 / 0 | 10 / 0 |
| 15 | 12 / 3 | 12 / 3 |
| 20 | 12 / 8 | 12 / 8 |

15/20 unassigned reasons all exceeds_shift_limit, zero P1 unassigned. Tasks were persisted via upload/correction using shared synthetic locations/labels: workflow acceptance, not new performance experiments.

| Check | Result |
| --- | --- |
| npm run lint | Passed |
| npm run test:ci | 10 files, 127 passed |
| npm run build | Passed; JS 682.86 kB/gzip 183.90 kB; >500 kB chunk warning retained |
| python SystemCode/frontend/scripts/export_contract.py --check | Snapshot matches current OpenAPI |
| python -m pytest SystemCode/tests -q | Final 979 passed/1 Windows symlink-permission skip, 52.09 s; Starlette TestClient deprecation warning retained |
| python .github/scripts/check_repository.py | 357 files passed |
| git diff --check | Passed |

Local checks retained existing training changes; 979 includes their uncommitted tests, not new tests in this PR. The separate PR contains decoder fix/regression and knowledge/acceptance docs only; remote CI checks actual delivery in a clean checkout.

## 4. Findings and fix

After first real-model load, Ultralytics 8.4.176 globally replaces PIL.Image.open. Corrupt PNG/invalid bytes trigger an optional HEIF branch; absent pi_heif caused ModuleNotFoundError/HTTP 500. Normal CI injects a fake model without importing Ultralytics and missed the combination.

Fix: capture Pillow's decoder reference during normal startup before lazy YOLO import, and use it for validation/second decode independent of global replacement. JPEG/PNG-only, EXIF normalization, limits/error contract remain; no HEIF plugin installed.

An HTTP regression reproduces invalid bytes after optional-library decoder replacement: failed before/passed after. The actual service then loaded real YOLO and returned 422 invalid_image for corrupt upload without records. 67 focused image/workflow tests passed, one Windows symlink skip.

Source changes required knowledge source-digest synchronization. Updated a-knowledge-v7 and corrected qa-03's stale “all real detections require review” claim. Six bodies/business-rule version unchanged. This does not complete RAG or verify all historical stage wording.

## 5. Unaccepted work and handoff

- **C GPT/RAG and crew preview/confirmation remain unimplemented**: no assistant backend routes; BC07/BC08 uncovered.
- **No real Google matrix call**: explicitly simulated matrix, no external usage. Existing fake-transport error tests do not replace real-service acceptance.
- SVG order schematic, geometry=null, no navigation polylines.
- Desktop browser only, no repeated mobile/cross-browser acceptance.
- Root rules/older guides retain historical B/C-pending wording; current progress follows this record/module READMEs. Clean stale knowledge-stage text before assistant ingestion.
- Weight, 60% gate, single box and P3/P2/P1 durations unchanged; model generalization remains separate work.

## 6. Evidence and runtime

Local only, Git-excluded Dataset/acceptance/integration-20261018/:

- api-acceptance.json/http-trace.json: final 20 groups, keys/statuses/responses.
- http_acceptance.py: executed local snapshot with browser preset IDs; not a generic importer to rerun against the normal DB.
- api-acceptance-before-fix.json/http-trace-before-fix.json: first failure; retry-preparation-trace.json closes prior test tasks.
- api-final-snapshot.json: 20 active test tasks/revision 53; four crews available and test plans retained for review.
- pytest-final.log: full regression; pytest-source-hash-before-sync.log: post-fix knowledge-digest issue.
- ui-real-inspection.png, ui-comparison-single.png, ui-map-20-tasks.png, ui-comparison-20-tasks.png: actual browser.
- Backend/frontend .log/.pid: service logs/process records.

To restart the same isolation, from root in a backend terminal:

```powershell
$env:ROADGUARD_DB_PATH='Dataset/acceptance/integration-20261018/workflow.sqlite3'
$env:ROADGUARD_UPLOAD_PATH='Dataset/acceptance/integration-20261018/uploads'
$env:ROADGUARD_TRAVEL_MATRIX_PROVIDER='simulated'
$env:ROADGUARD_VISION_MANIFEST_PATH='SystemCode/model/releases/roadguard-single-v1.json'
.\.venv\Scripts\python.exe -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8001
```

Frontend terminal, Node 22.x ≥22.12 and npm, from root:

```powershell
cd SystemCode/frontend
npm ci
$env:ROADGUARD_API_TARGET='http://127.0.0.1:8001'
npm run dev
```

If these services occupy ports, open existing URLs rather than duplicate startup. All configuration targets the isolated DB, separate from normal 8000/database settings.
