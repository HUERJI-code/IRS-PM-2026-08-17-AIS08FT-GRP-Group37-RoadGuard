# RoadGuard frontend · C steps 2–9

2026-10-18: The approved review and crew-workspace style now covers sign-in, upload, inspection details, tasks, routes, comparison and the assistant placeholder. White/warm-grey surfaces, dark text and restrained green accents are used throughout. Mobile navigation follows account permissions; task details, map section links and horizontal comparison tables support narrow screens. Existing permissions and business actions are preserved. See [visual preview](DESIGN_PREVIEW.md) for coverage, viewing instructions and the latest 152-test/browser acceptance record. The user approved delivery through PR/CI together with the required authentication backend. Update frontend and backend together. Each member creates accounts in their own database following [account roles](../../Miscellaneous/ACCOUNT_ROLES.md); passwords and runtime data are not synchronised through Git.

The initial usability refinements retain write-operation protections. At the project owner’s request, course-specific wording was removed from the interface. Actual mock-data, experimental-model and schematic-route provenance remains visible; backend rules and provenance fields are unchanged. Older test counts, data counts and “uncommitted” statements below and in stage documents describe those stages. The latest delivery scope is stated above and in the visual preview.

2026-10-19: Interface copy, accessibility names, tests, comments and frontend documentation have been translated into English. Document and numeric/date formatting locales use `en-SG`; times remain in `Asia/Singapore`. Stable API fields, identifiers and permissions are preserved.

## Current workflow

1. **Upload inspection:** prepare a clear road photo, its Jurong coordinates and a road declaration. A real primary detection meeting the backend threshold (currently 60%) creates a task automatically; lower confidence enters review, and no detection creates no task. Mock detection requires explicit selection.
2. **Manual review:** process only the pending queue. Check the selected photo and confirm, correct or reject it. Confirmed/corrected tasks enter the task workspace.
3. **Repair tasks:** select a task in the queue, check damage, priority, duration and provenance, then save required changes. Completed/cancelled records remain under their filters.
4. **Four-crew routes:** check crew availability and explicitly recalculate. Desktop prioritises the map and overview with crew/recalculation controls alongside; narrow screens stack sections. The map illustrates stop order and must not be used as road navigation.
5. **Algorithm comparison:** enter from the current recalculation to compare task coverage before time metrics. Same-run evidence, stale status and unassigned tasks remain visible. Refreshing or changing sources does not infer a same-run match from timestamps.
6. **Crew workspace:** use the account-bound crew’s latest saved GA schedule. Check stop order and current tasks, then record completion. Mobile provides a collapsed menu, single-column details, large controls and a route shortcut. Completion retains the saved route and flags it as stale; dispatch explicitly recalculates. See [crew guide](CREW_GUIDE.md).

Expandable page help provides the current step and complete workflow. The service bar shows permitted live/mock source controls and the last connection check; diagnostics are expandable. A successful check does not establish model, Google or assistant readiness. Queues and details sit side by side on desktop; selecting a mobile record focuses its details after loading. Inspection results use shared damage display names, role-specific next actions and expandable provenance/original backend rule records. The assistant is explicitly marked as in development.

Styles retain `src/styles.css` and `src/workspace.css`; the last-imported `src/refined-workspace.css` unifies the site and mobile presentation. No font download or extra dependency is introduced. Crew colours reuse map `crewColor` rather than card order.

Local checks on 2026-10-18 with Node 22 passed lint, 130 component/client tests, TypeScript and Vite build. Added tests cover full workflow navigation and mobile focus after asynchronous task/review loading without repeated scrolling on reread. The main JS chunk still exceeds 500 kB; dependencies and chunk splitting were unchanged.

The main agent verified desktop flows against an isolated integration database: real photo upload, low-confidence review, correction to a pothole creating a P2/120-minute task, task completion/removal from the active queue, explicit 20-task recalculation and same-run comparison. The new test task was completed and retained in history. The active queue contained 20 tasks, four available crews and input revision 55. At 390×844, upload, task, dispatch and comparison pages had no whole-page horizontal overflow; task selection and review deep links focused loaded details correctly. Explicit mock failure showed an error rather than empty data, and the assistant remained unavailable. Evidence is in ignored local directory `Dataset/acceptance/frontend-preview-20261018/`. No real Google/GPT calls, training or routine-database changes occurred. Preview `http://127.0.0.1:5173` proxied to isolated backend port 8001. This was not production, cross-browser or physical-device acceptance.

Owner: C. Implemented React + TypeScript foundations, seven workspace categories, responsive layout, basic accessibility and real health checks. Step 4 adds upload/results and linked tasks ([upload guide](UPLOAD_GUIDE.md)); step 5 adds [review](REVIEW_GUIDE.md); step 6 adds [task management](TASK_GUIDE.md); step 7 adds [crew controls and explicit recalculation](PLANNING_GUIDE.md); step 8 adds the [map](MAP_GUIDE.md); step 9 adds [same-run GA/Greedy comparison](COMPARISON_GUIDE.md). The assistant remains pending. Step 3 introduced the shared client, generated OpenAPI types, response validation and explicitly selected read-only mock examples ([API client](API_CLIENT.md)).

## Start on macOS

Use **Node 22 + npm**, matching CI. Node must be 22.12 or later within 22.x. With nvm installed, use `.nvmrc` through `nvm use`; otherwise install official Node.js 22.x. Check:

```sh
node --version
npm --version
```

From repository root:

```sh
cd SystemCode/frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://127.0.0.1:5173`. The environment file is optional; backend target defaults to `http://127.0.0.1:8000`. Set `ROADGUARD_API_TARGET` in `.env.local` and restart to change it. An occupied port fails explicitly rather than selecting another port. Stop with Ctrl+C.

Start the existing FastAPI app in another terminal from repository root (activate an existing environment rather than recreating it):

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r SystemCode/backend/requirements.txt
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend --host 127.0.0.1 --port 8000
```

Health checks do not require vision dependencies or inference. Prepare real-model dependencies separately using the [backend guide](../backend/README.md). Backend startup initialises/validates its database as designed; never delete an existing database as disposable test data.

## Pages and connection behaviour

| Frontend path | Content |
|---|---|
| `/` | Redirect to the role-appropriate workspace |
| `/inspections/new` | Photo, mode, coordinates and road declaration upload |
| `/inspections/:inspectionId` | Inspection result, single-box image and linked task |
| `/reviews` | Pending queue, confirmation, correction and rejection |
| `/tasks` | Task list, details and status management |
| `/routes` | Crew controls, explicit recalculation, Jurong map and route details |
| `/comparison` | Same-run verification, metrics and unassigned-reason comparison |
| `/crew?crew=crew-02&algorithm=ga` | Account-bound crew route, current tasks, progress and completion |
| `/assistant` | Route-assistant placeholder |
| Other paths | 404 and workspace link |

Pages automatically make the read-only `GET /api/v1/health` call with loading, success, failure, eight-second timeout and manual retry states. The source panel explicitly selects live/mock data. Only opening “Check data connection” and clicking its button reads the active snapshot and latest GA plan. App/database success does not establish model, Google or assistant readiness. Failures do not fall back to mock; “not connected” is different from an empty task list.

Vite development and local preview proxy `/api` unchanged to the backend, without changing backend CORS. Backend keys never enter the browser. `ROADGUARD_API_TARGET` is server-only and avoids the client-exposed `VITE_` prefix.

Production must reverse-proxy `/api` to the same FastAPI app and fall back to `index.html` for page routes so deep links refresh correctly. `npm run preview` is a local build check, not a production server.

## Checks and dependencies

```sh
npm run lint
npm run test:ci
npm run build
npm run preview
```

Preview uses `http://127.0.0.1:4173`. `npm test` watches in development; CI uses single-run `test:ci`. Tests cover seven-page navigation, home redirects, direct routes, 404, health loading/success/failure/retry, invalid responses, timeouts and cancellation on unmount. Client/source tests are described in API_CLIENT.md. Backend business tests are separate.

- React/React DOM render components; React Router handles navigation/history.
- Vite/React plugin and TypeScript provide proxy, builds and type checks.
- ESLint/TypeScript/React rules provide static checking.
- Vitest/jsdom/Testing Library exercise actual component/network interactions.
- Versions are pinned in package.json with one package-lock.json; reproduce with `npm ci`. Existing CI discovers the frontend and runs lint, test:ci and build; no `.github` change is needed.

## Handoff boundary

Frontend work stays in `SystemCode/frontend/` without changing A/B APIs, database or business configuration. Workspaces do not invent tasks, routes or metrics. Assistant interactions remain future work. Older shared statements that “frontend is not implemented” refer to the incomplete full application; this guide states the implemented foundation.

## C planning and page design

The [14-step plan](docs/C_TASK_PLAN.md), [page flow](docs/PAGE_FLOW.md), [initial API mapping](docs/API_MAPPING.md) and [open questions](docs/OPEN_QUESTIONS.md) retain their planning baseline. Steps 1–9 are implemented; module guides define validation boundaries.

## Account-based access

Sign-in was added on 2026-10-18. Inspectors upload and view their own results; crew accounts bind to one crew; central dispatchers access review/tasks/four-crew routes/comparison/assistant. Update frontend and backend together. Account provisioning, cookies/CSRF and permissions are in [account roles](../../Miscellaneous/ACCOUNT_ROLES.md); operations are in the [crew guide](CREW_GUIDE.md). There is no role selector or self-registration. Expired sessions return to sign-in. Mobile supports account details and sign-out.
