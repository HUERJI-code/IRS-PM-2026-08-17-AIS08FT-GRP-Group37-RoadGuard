# Crew workspace

2026-10-18 · Local preview · Account-bound version. Owner: A coordinating frontend extension and integration acceptance.

## Sign-in and operations

- Sign in with a crew account to enter `/crew`. Account B, for example, binds to `crew-02`. There is no crew/algorithm selector or dispatch/upload entry. URL parameters cannot change the binding.
- The workspace reads the central dispatcher’s latest saved GA plan and shows only this crew’s stops, tasks and photos. If unassigned, wait for dispatch rather than generating a plan.
- Follow saved order and inspect pending tasks, damage type, duration, priority, recommendation, current location and planned arrival. Select a stop for details.
- Select “Mark as complete”, check the task and “Confirm completion”. Status/progress updates while history remains; continue to the next task. Completed/cancelled tasks are read-only.
- “Refresh workspace” reads the latest schedule. “Reload task status” checks the current route. A newer dispatch plan requires workspace refresh before further actions.
- Mobile retains account, crew and sign-out with collapsed navigation, single-column content and a collapsed map. Main completion control is 52 px; task/confirmation buttons are at least 44 px. Selecting a task focuses its details.

## Snapshots and permissions

`GET /api/v1/crew/workspace` returns the bound crew, crew-only plan, current tasks and input_revision in one transaction. Global crews, routes and task lists return 403 to crew accounts.

Changed task location/duration is flagged against the snapshot. Completion increments input_revision and makes the old plan stale, but valid, un-reassigned crew tasks may still be completed. Dispatch explicitly replans; the workspace never automatically recalculates. Stop order/times are estimates, not live remaining work.

For crews, `PATCH /api/v1/tasks/{task_id}` accepts only expected_version, fixed request_id and status=completed. The backend validates latest assignment, availability, version and state in one write transaction. Former crews cannot complete reassigned tasks. Duplicate submission does not duplicate changes. Uncertain network outcomes retain the request, lock switching/refresh and retry the original request.

Task details/photos also enforce server-side ownership. After actual completion, crew completion receipts allow reads/retries. Original task/review history is retained. See [account roles](../../Miscellaneous/ACCOUNT_ROLES.md) for accounts, sessions and audit rules.

The map shows frozen Jurong boundaries, NUS-ISS and this crew’s route. Straight lines illustrate sequence, not navigation or GPS. There is no separate publication step: the latest saved GA plan is authoritative for the workspace.

## Local acceptance and limitations

Pre-authentication component/browser records remain in ignored `Dataset/acceptance/crew-workspace-20261018/`. Account-version credentials, backups, screenshots and actual checks are in `Dataset/acceptance/auth-roles-20261018/`. Dataset, credentials and runtime databases are not committed.

The isolated integration database was backed up before migration and its input_revision retained. Real authorisation tests cover cross-crew access, reassignment, disabled crews, revision conflict, idempotent retry and session checks. Frontend tests cover fixed crew, unknown-outcome retry, final-state read-only records, missing tasks, stale plans, role navigation, account switching and mobile focus.

Local services listen only on loopback. Mobile layout does not establish mobile-network access, physical-device or production acceptance. Deliver this workspace with the frontend and account-permission APIs: update both ends and create local accounts.
