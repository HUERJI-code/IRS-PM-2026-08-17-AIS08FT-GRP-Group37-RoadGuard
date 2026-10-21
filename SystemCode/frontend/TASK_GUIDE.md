# C step 6: Task list, details and status management

2026-10-16; owner C. Scope is SystemCode/frontend only; A/B backend, APIs and the shared label dictionary are unchanged.

## Implemented behaviour

- /tasks shows active, completed, cancelled or all tasks, with server filters, 20-record pagination and page input revision. /tasks?task={id} links directly to a review-created task.
- Details reload the latest record and display location, label, severity, priority, estimated repair duration, deadline, rule version, recommendation and Singapore time. The original-inspection link provides detection/rule evidence.
- Active tasks support completion, cancellation, label correction and location correction. Labels use the shared eight-class dictionary. Location submits latitude, longitude and road_type together and requires a public-motor-road declaration. Backend checks the Jurong boundary.
- priority, service_minutes and due_at have no arbitrary edit controls. Unknown duration displays “Unknown”; null deadline displays “Not set”.
- Final-state records retain history, are read-only, cannot reactivate and are excluded from new plans. History includes changed fields and before/after values.
- Every change carries request_id and expected_version. Submission blocks duplicates; uncertain outcomes retain the original request for retry. Version/state conflicts require rereading/checking rather than applying old intent automatically.
- Success refreshes the list and retains the save result. A subsequent list-read failure is not reported as a failed write. Input changes/replay prompt checking and replanning old routes; this page does not recalculate automatically.
- Read-only mock sources block edits; failures never automatically fall back to mock.

## API

| Purpose | Request |
|---|---|
| List | GET /api/v1/tasks?status=active/completed/cancelled/all&limit=20&offset=0 |
| Details/history | GET /api/v1/tasks/{id} |
| Change | PATCH /api/v1/tasks/{id}; request_id, expected_version and permitted changed fields |

## Files

Added TaskPage.tsx, TaskPage.test.tsx, task-fixtures.json and export_task_fixtures.py; updated App.tsx routing, styles, navigation and source tests. Node 22/npm and existing dependencies remain; no dependencies added.

## Validation and limitations

Temporary-backend validation covered completion, cancellation, label/location correction, no-op changes, stale-version conflict and replay. Replay did not duplicate history; final states left the active snapshot. Synthetic PNG/demo detection were used without running real models or changing ordinary project data.

Project-write and local-server-start permissions were withdrawn during this stage; existing changes remained. Final checks ran on an identical copy in an allowed writable directory (results below). The browser read active tasks; task-submission browser acceptance had not yet been repeated at this stage, although automated interactions passed.

Unknown-outcome retry data lives only in page memory. Do not change sources/pages or refresh before resolving it. Build retains the >500 kB chunk warning.

## Delivery and next steps

At this stage feature/c-frontend-foundation remained uncommitted/unpushed. Steps 2–6 were retained and this guide was saved in Codex outputs; the repository guide was restored on 2026-10-17.

Steps 7–8 were subsequently restored to the original project and dispatch/map browser acceptance completed; see BROWSER_ACCEPTANCE.md.

## Final acceptance addendum

- Identical copy: lint, all 72 tests in six files and build passed. Source/configuration matched the original project file by file.
- Seventeen new interaction tests cover four action payloads, complete road declaration, conflict refresh, original-request retry, duplicate protection, final-state read-only behaviour, unknown values, mock-write blocking, filters/pagination and list-refresh failure.
- JS 536.82 kB, gzip 150.01 kB; >500 kB warning retained.
- Original-project git diff --check passed; changes stayed within frontend.
