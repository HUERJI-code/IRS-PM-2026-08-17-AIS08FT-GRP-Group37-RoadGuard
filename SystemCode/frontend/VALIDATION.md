Latest: 2026-10-17, step 9 completed with 127 frontend tests, lint, build and browser acceptance. See COMPARISON_GUIDE.md. Steps 7–8 were restored and browser-verified (BROWSER_ACCEPTANCE.md). Historical stage records follow.

# C step 2 acceptance

2026-10-15; owner C; main f8a2cf3; feature/c-frontend-foundation.

| Check | Result |
|---|---|
| Node/npm | Node 22.23.3, npm 10.9.9; official Node archive SHA-256 verified |
| npm ci | Installed from the single package-lock.json |
| lint | Passed without warnings |
| test:ci | One file, ten passing tests |
| build | TypeScript and Vite passed |
| Real local health | Vite 5173 → FastAPI 8000; status=ok, database=ok, api_version=v1, input_revision=0 |
| Build preview | Port 4173 /comparison deep link and /api/v1/health returned 200 |
| Browser | Desktop and 390×844; document width=viewport width=390, no overflow; assistant navigation worked |
| Git scope/whitespace | Only frontend additions/changes; git diff --check passed |

Tests cover default task entry, all six navigation entries/active state/title/focus, direct routes, 404 return, health loading/network retry/HTTP failure, non-JSON/invalid DTO, eight-second timeout and unmount cancellation. Component tests use explicit fetch doubles; separate browser checks connected real FastAPI.

Health checks used a temporary Python 3.12 environment and isolated empty SQLite, leaving ordinary data unchanged. Python 3.11 CI baseline is unchanged; full 3.11 backend acceptance was not claimed. Vision was disabled; no model/Google/GPT calls. Health success does not establish those capabilities.

At this stage local changes were uncommitted/unpushed with no PR/remote CI. Existing CI detects package.json and runs npm ci/lint/test:ci/build. Step 3 would build client/types/explicit mock modes; upload/review/task/map/comparison/assistant interactions were not yet connected. Cross-module assistant-confirmation dependencies remained in the step 1 open list.

# Step 3 addendum

2026-10-15: Continued the same local branch without overwriting others’ changes.

Added backend-exported OpenAPI/generated types and matching JSON Schema validation; 16 JSON client methods plus image resolution for 17 endpoints (assistant proposals excluded); structured errors, cancellation/timeouts, operation-ID reuse, revisions, minute/millisecond and Singapore-time helpers; isolated synthetic snapshots for normal/empty/failure/conflict modes with all mock writes rejected; explicit source selector/manual read-only checks that cancel/clear on source changes.

| Check | Result |
|---|---|
| npm ci | Reproducible lockfile passed |
| lint | Passed |
| test:ci | Three files, 29 tests including step 2 |
| build | Types and production build passed |
| export_contract.py --check | Backend OpenAPI matched snapshot |
| Normal/empty schemas | Passed; examples generated from real backend response models |
| Real HTTP client | Via Vite: health, empty tasks, snapshot, four crews, seven demo scenarios; missing plan correctly recognised 404 route_plan_not_found |
| git diff --check | Passed |

HTTP used the previous isolated empty database without real-photo uploads/business changes. A separately cleaned temporary database generated demo uploads/simulated plans without external calls. Python remained 3.12; no full 3.11 test claim.

Browser tooling could not load its connection policy in this stage, so the new panel’s visual review was incomplete. Testing Library source interactions and separate real HTTP checks passed; this limitation must not be recorded as browser acceptance.

API_CLIENT.md explains type updates/mock restrictions. Read-only snapshots do not implement a writable state machine; future upload demonstrations require isolated scenarios. Business pages were still skeletons, not end-to-end dispatch. A/B files/APIs unchanged. TypeScript changed to 5.9.3 for generator peer compatibility; Node/npm unchanged. Steps 2–3 stayed local with no PR/remote CI.

# Step 4 addendum

2026-10-16: Upload, result details, single overlay and linked-task reads connected.

- After correcting a TypeScript conditional-rendering error, lint, 43 tests and build passed.
- Real FastAPI through Vite verified three demo uploads: first 201, same-key replay 200, details/image/task links.
- Browser completed demo upload; mobile overlay/image dimensions matched without overflow.
- Only synthetic demo records in an isolated database; no ordinary-data changes or real inference.
- Build passed with the visible >500 kB chunk warning.

See UPLOAD_GUIDE.md. Steps 2–4 remained local/uncommitted/unpushed.

# Step 5 addendum

2026-10-16: Queue, latest details, confirm/correct/reject, history and conflicts connected.

Lint, 55 tests in five files and build passed. Real HTTP verified all actions, stale 409, replay and single history entry. Browser correction created a task; 390-pixel layout had no overflow. Isolated synthetic demo data only; no real model/ordinary-data changes. Size warning retained; retry lives in memory. See REVIEW_GUIDE.md. Frontend only, local/uncommitted/unpushed; task management followed.

# Steps 6–7 addendum

Step 6: 72 frontend tests passed. Step 7: 15 additions plus temporary-backend checks of stale revisions, idempotent crew save, stale plans, same-run recalculation and all crews unavailable. See PLANNING_GUIDE.md. At this point step 7 existed only in the Codex copy pending restoration; port permissions blocked browser acceptance.

# Step 8 addendum

2026-10-17: Frozen boundaries, external depot, ordered crew lines/returns, map/details and unassigned tasks implemented in the working copy. Thirteen additions; see MAP_GUIDE.md. Original-project restoration/browser checking were still pending due to port restrictions.

# Steps 7–8 restoration and browser acceptance

2026-10-17: Cumulative patch applied to original groupwork1; steps 2–8 on local feature/c-frontend-foundation, uncommitted/unpushed. Do not reapply. Lint, 100 tests/eight files and build passed. JS 670.51 kB, gzip 179.93 kB; >500 kB warning retained.

Browser used original Vite/FastAPI with isolated frontend-check.sqlite3, synthetic inspections/simulated matrix. Disabling crew-01 changed record 1→2/input 5→6; same-run recalculation assigned all five tasks to three other crews. Crew/stop-2 selection synchronised map, durations, times and task link. At 390×844 document width 375 ≤ 390; full Jurong/depot, wrapping, focus and reset worked. Restoring crew-01 advanced input to 7 and marked old plans stale; recalculation/algorithm switch worked. Default viewport restored, all crews available.

Final isolated plans: GA plan-313e2b682ae7447ab83b176acf463bb3; Greedy plan-e1a65a69915f4d558c4d3b72f69fb32f; revision 7. Not algorithm evaluation data. No real model/Google/GPT calls, A/B edits or ordinary-database changes. Step 6 browser submission not repeated; automated tests passed. Step 9 comparison followed.
