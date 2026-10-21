# Accounts, pages and API permissions

2026-10-18 · A coordinates shared authentication/frontend integration. The user explicitly requested separate workspaces by account. This module ships with the approved unified frontend and crew workspace; frontend/backend must update together.

## Three account types

| Role | Landing page | Allowed | Not allowed |
|---|---|---|---|
| `inspector` | `/inspections/new` | Upload one photo; view own inspection results/photos | Global inspection/task lists, review, dispatch, task changes |
| `crew` | `/crew` | Own fixed crew's latest GA route/tasks/photos; complete own tasks | Switch crews, global lists, label/location changes, cancellation, recalculation |
| `dispatcher` | `/tasks` | Review, tasks, four-crew management/planning, comparison, assistant entry | Photo uploads, crew workspace |

Inspection details belong to their parent workflow: inspectors read only their own; crews read inspections for accessible assigned tasks; dispatchers read all. The route assistant is dispatcher-only. Knowledge queries, saved-plan explanations, crew availability changes and task reassignment/cancellation enforce the same session, role and CSRF checks as other protected operations.

Frontend navigation/page guards follow the server account. Backend authorization is independent; URL, headers or frontend state cannot bypass it. `/crew?crew=crew-01` does not change account binding. Workspace APIs accept no client-selected crew or algorithm.

## Provision local accounts

There is no public registration, default password or startup-created account. The project owner runs these PowerShell commands from the repository root; passwords are hidden at the prompt and must be 12–256 characters.

```powershell
$env:PYTHONPATH = 'SystemCode/backend'
# If the backend uses a custom database, set the same ROADGUARD_DB_PATH.
.\.venv\Scripts\python.exe -m roadguard.auth.manage create a --name 'Inspector A' --role inspector
.\.venv\Scripts\python.exe -m roadguard.auth.manage create b --name 'Crew 2 · B' --role crew --crew crew-02
.\.venv\Scripts\python.exe -m roadguard.auth.manage create c --name 'Central Dispatcher C' --role dispatcher
```

Usernames are case-insensitive, at most 32 characters, using English letters, digits, periods, underscores and hyphens. Role/crew are server-configured only. Other crews bind to `crew-01`, `crew-03`, `crew-04`; multiple people may have separate accounts for one crew. Pulling the repository does not share accounts: create them in the actual runtime database.

Reset: `python -m roadguard.auth.manage password b`. Disable: `python -m roadguard.auth.manage disable b`. Both revoke the account's sessions. `--generate-password` generates locally and displays once; do not save it in committable files. No web account management or password recovery exists.

## HTTP and Swagger

| Endpoint | Response/action |
|---|---|
| `POST /api/v1/auth/login` | `{ "username": "a", "password": "locally configured password" }`; sets HttpOnly Cookie; returns `user`, `csrf_token`, `expires_at` |
| `GET /api/v1/auth/session` | Current account/CSRF token; 401 if missing/expired |
| `POST /api/v1/auth/logout` | Revoke session/clear Cookie; requires `X-CSRF-Token` |
| `GET /api/v1/crew/workspace` | Fixed `crew`, own latest-GA `plan`, current route `tasks`, `input_revision`; `plan=null` if absent |

`user` contains only account ID, username, display name, role and nullable crew_id. Authentication `expires_at` is Unix seconds; business timestamps remain timezone-aware ISO 8601. Workspace `plan` contains only this crew's route and depot/time/source, not other crews, global matrix or global metrics.

In `/docs` on the same hostname, log in first; the browser retains the Cookie. Copy `csrf_token` into `X-CSRF-Token` for upload/review/completion. GET needs no CSRF. To switch roles, log out then log in. Reauthenticate on 401; 403 means role/CSRF/origin disallowed; 404 may mean absent or inaccessible. Do not mix `localhost` and `127.0.0.1` Cookies.

Script clients retain login Cookies and send `X-CSRF-Token` for writes. Business APIs no longer support anonymous clients. `/health` and OpenAPI remain anonymous. Add every new business route to `auth/dependencies.py`'s permission table or it is denied by default.

## Ownership, concurrency and auditing

- SQLite migrates incrementally from v3 to v4, adding `auth_users`, `auth_sessions`, `auth_login_limits`, `inspection_owners`, `auth_audit`; inspections/tasks/images/plans/request keys/input_revision remain, without database recreation. Initial migration needs a write lock; close uncommitted viewer transactions before startup.
- New uploads record inspector ownership in the same transaction. Upload/review/completion idempotency keys are account-scoped. Legacy inspections have no verified uploader and are not assigned to the first login; dispatchers retain access and crews access through task assignment.
- Assignment uses the latest saved GA plan. No separate publication step exists: saving GA changes the workspace source. An input_revision change alone flags an old snapshot but does not block completion of valid tasks still assigned to the crew.
- Completion checks account validity, latest-GA assignment, the current durable task-to-crew constraint, crew availability and task revision/status in the same write transaction, preventing stale-page actions after reassignment. An original committed completion can be retried after recalculation using its crew completion receipt; no repeated mutation or automatic recalculation.
- Completion writes `auth_audit` account/task/request/crew/plan/time and task history `actor_source=authenticated_user`. Legacy `user_declared_unverified` retains its meaning; authenticated identity is not engineering qualification certification.

## Sessions and configuration

Passwords use standard-library scrypt (N=2^17, r=8, p=1, random salt); only hashes are stored. Sessions are random 32-byte values with only SHA-256 digests stored and eight-hour expiry. Cookies use HttpOnly/SameSite=Strict; writes validate session-bound CSRF and request origin. Passwords/tokens are not in frontend localStorage; cross-tab storage contains only credential-free change notifications.

Login limits count 10 attempts/account and 60/source address per 15 minutes in the database; success clears the account count. Clients behind Vite may share an address count. This currently supports local project previews. External deployment should use HTTPS and `ROADGUARD_AUTH_COOKIE_SECURE=true`; comma-separated `ROADGUARD_AUTH_ALLOWED_ORIGINS` lists actual frontend origins. Defaults allow only local 127.0.0.1/localhost on 5173, 4173, 8000, 8001, without automatically opening LAN access.

References: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html). SSO, MFA, self-service management and formal production deployment are not included.

## Acceptance entry points

Real-auth tests: `python -m pytest SystemCode/tests/test_auth.py -q`, covering anonymous denial, all roles, upload ownership, cross-crew denial, reassignment/disablement, CSRF, session revocation/expiry, rate limits, idempotent completion and data-preserving v3 migration.

Frontend: `npm run lint`, `npm run test:ci`, `npm run build`, covering login/retry, role navigation/direct URL protection, clearing old account pages, cross-tab session changes, fixed crew workspace and mobile task selection.

Historical business tests/synthetic exports explicitly use isolated test identities from `SystemCode/tests/auth_test_support.py`; production never loads that override. Account-security tests use real login/Cookies without overriding authorization dependencies. Update frontend/backend together and adapt old anonymous scripts to login.

## Confirmed task adjustment access

A confirmed reassignment immediately removes the previous crew's task/inspection read and completion access. The target crew obtains access only after an explicit saved GA recalculation assigns the task to it. The affected old route is omitted with a stale/recalculation explanation. Inspectors and crew accounts cannot preview, confirm, discard or recalculate dispatcher changes. Cancellation retains task history and excludes terminal work from active planning; it does not reopen completed or cancelled tasks.
