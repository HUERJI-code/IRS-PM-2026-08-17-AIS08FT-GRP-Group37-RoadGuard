# Unified site design and mobile preview

2026-10-18. Owner: A coordinating acceptance in C’s frontend module. The user confirmed the site preview and approved delivery through an English PR, CI and auto-merge.

Delivery includes current frontend, crew workspace, required authentication backend, tests and API docs. Sessions, inspection ownership and crew permissions require backend enforcement, so fetch these changes together. Create accounts in each member’s runtime database ([account roles](../../Miscellaneous/ACCOUNT_ROLES.md)). Uncommitted model-training changes, Dataset, private account files and runtime databases are excluded. Browser records below describe local acceptance, not production deployment.

## Design direction

Used the [distinctive-ai-design](https://github.com/houxin0010/distinctive-ai-design) design/screenshot-review workflow. This developer-local skill is not a frontend runtime dependency and team members do not need to install it.

- Users/tasks: inspectors upload photos/locations and view results; dispatchers check evidence, manage tasks and four-crew routes; crews view their own routes/current tasks and record completion.
- Intended feel: clear, quiet and dependable, using white/warm grey, dark text and restrained green for primary actions.
- Hierarchy: pending queue, photo evidence and review actions; mobile crew account, progress, current task and stop order.
- Interactions: retain confirm/correct/reject, notes, provenance/rule evidence; add crew-route shortcut and stop-to-task navigation.
- Avoid decorative backgrounds, repeated instructions, nested cards and unnecessary generated images/motion.
- Following approval of review/crew styling, extend the same colours, containers, forms, menus, buttons, focus and empty states to sign-in, upload, inspection details, tasks, routes, comparison and assistant placeholder.

## Implementation boundary

`src/refined-workspace.css` scopes effects using `.refined-shell` and page classes. Existing React/client/image/route components are reused without new dependencies.

Mobile menus collapse after navigation and remain role-filtered. Identity and sign-out stay visible. Full workflow help is expandable. Tasks reuse the review queue/details structure and focus selected details on mobile.

Upload form/help stack on narrow screens. Input font sizing avoids mobile-focus zoom. Mobile sign-in prioritises the form. The map precedes crew controls with route-map/control section shortcuts. Full IDs/times sit in provenance details while simulated/external source, revision and stale warnings remain visible. The comparison table scrolls locally and retains a readable first column.

Review workflow help is expandable with complete provenance/IDs. Photos and forms sit side by side on wide desktops and stack when narrower. Empty queues and no selection are distinct states.

Crew mobile combines title/refresh and removes repeated guidance. Plan origin/start remain under times/sources. Route shortcut focuses itinerary; choosing a stop focuses the task. Completion still requires confirmation.

APIs, sessions, roles, crew binding, single-box policy, 60% threshold, rules, idempotency, conflict and uncertain-result retries are unchanged. Server rejects unauthorised access. The workspace reads the account-bound crew’s latest GA schedule.

## Viewing

Local preview: `http://127.0.0.1:5173`, proxying to the existing isolated integration backend on 8001.

- Dispatcher `c`: `/reviews`, selecting a pending photo/action; also `/tasks`, `/routes`, `/comparison`, `/assistant`. Assistant remains explicitly in development.
- Inspector `a`: `/inspections/new` and own results.
- Sign out and use crew `b`: `/crew`, fixed to `crew-02`; inspect mobile viewport.
- Passwords remain in the existing local private account file, never this guide or Git.

An earlier review-page acceptance added one pending inspection in the isolated database using a previously uploaded road photo and explicit `demo / low_confidence` synthetic detection. It is labelled mock detection, not model evaluation or a real Jurong inspection. No repair task was created; revision remained 56. Pre-change backup, provenance, screenshots/checks are in ignored `Dataset/acceptance/design-refresh-20261018/`.

This unified-site stage added no records or review/completion/recalculation writes. Current active tasks: 19; input revision 56; saved route revision 55. Stale warnings were retained instead of recalculating for screenshots. Screenshots, boundary checks and acceptance records are in ignored `Dataset/acceptance/unified-design-20261018/`.

## Completed checks

- Node 22 lint, all 152 tests and build passed. Existing >500 kB main-JS warning remains.
- Existing review tests cover confirmation/correction/rejection, conflict, uncertain retry and mock-write protection. Crew tests cover binding, completion confirmation/retry, unavailable crews, changed routes, stale state and mobile focus.
- New route-shortcut test checks focus/scroll without task changes/completion.
- Added shared-menu expansion, collapse after navigation and dispatcher-entry tests. Map-source tests verify external provenance when collapsed and full source/IDs after expansion.
- Browser: real local sign-in; complete desktop photo/single overlay; corrected-label selection/rejection help; mobile route shortcut, stop selection, completion confirmation/cancellation. Crew widths 390/360 and review width 390 had no whole-page overflow; completion button was 52 px high.
- API checks: inspector task queries, crew review-queue queries and dispatcher crew-only workspace access all returned 403.
- Two independent screenshot-review rounds corrected duplicate mobile header information and secondary-text contrast. Functional checks were separate from visual judgements.
- Two further rounds after site-wide extension compacted mobile account bars, collapsed full map provenance, unified sign-in branding/table focus and evenly arranged mobile map controls. At 360/390 widths, upload, details, review, tasks, routes, comparison, crew and assistant had no whole-page overflow. Map zoom, section links, task forms, role menus and completion confirmation/cancellation worked.
- Actual local a/b/c sign-ins: a saw upload only; b saw bound crew only and could not read a’s unassigned inspection; c saw dispatch entries. Permission logic, API and backend configuration were unchanged.

No review/completion write was submitted in this browser stage; existing component tests validate those operations. No physical-device, cross-browser or full screen-reader acceptance. Visual work did not train models or change backend code; delivery includes previously implemented required auth code while training changes remain local.
