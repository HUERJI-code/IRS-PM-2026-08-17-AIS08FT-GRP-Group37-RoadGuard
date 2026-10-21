# C step 5: Manual review

Owner C; 2026-10-16. The review workspace connects the existing backend. Changes stay in SystemCode/frontend without altering A/B APIs, models, rules or database structure.

## Workflow

1. Open http://127.0.0.1:5173/reviews and select the live backend, or follow a pending-inspection result link.
2. The pending list shows 20 records per page with refresh/pagination. Selecting a record reloads full details and current record_version.
3. Check the single box on the server image, model label/confidence, rule source and history. Confirm, correct the label and accept, or reject. Correction options read the shared eight-class dictionary without copying business mappings.
4. Add an optional note up to 500 characters. Success refreshes the queue and shows the returned inspection, linked task, planning-input revision and review history.
5. Confirmation/correction shows backend priority and repair minutes; rejection creates no task. Confirmation/correction automatically attempts paired GA/Greedy planning after the task commits; dismissal triggers none. A planning failure retains the task and old stale plans and shows a manual-retry warning.

Original model labels/confidence remain evidence; corrections appear in linked tasks and review history. Processed records are read-only and cannot be reviewed again. Loading, an actual empty queue, failures and potentially stale retained lists are distinct. Top-level mock sources are read-only and cannot save.

## API and concurrency

| Action | Endpoint or fields |
|---|---|
| Queue | GET /api/v1/inspections; status=pending_review, limit=20, offset |
| Current details | GET /api/v1/inspections/{inspection_id} |
| Review | POST /api/v1/inspections/{inspection_id}/review |
| Every action | request_id, expected_version, action; optional note |
| confirm | Include detection_id; omit damage_label |
| correct | Include detection_id and damage_label |
| dismiss | Omit detection_id and damage_label |

Submission blocks duplicate clicks. Unknown outcomes retain the original payload/request_id, lock editing and permit retry of only that operation; replay is visibly identified. Stale revisions, invalid state and idempotency conflict stop writes. Reload/check the record, clear old intent and choose a new action.

Retry data lives only in page memory. Closing/refreshing warns but cannot restore it. Remain on the current record for uncertain outcomes; do not change sources or pages. Other queue records are disabled during submission/uncertainty. Reopening the page does not recover the previous request.

## Validation results

- npm run lint, npm run test:ci and npm run build passed: five test files, 55 tests.
- Twelve new review tests cover action fields, eight shared labels, new requests after stale-version refresh, original-request retry, duplicate submission, processed read-only records, blocked mock writes, pagination and retained data on refresh failure.
- scripts/export_review_fixtures.py uses the existing app and a temporary database to generate three actions/replays, validated against the same OpenAPI JSON Schemas.
- The shared client connected through Vite to real FastAPI. All three actions passed; wrong expected_version returned 409 stale_record_version; replay created no duplicate tasks/reviews. confirm/correct linked tasks; dismiss returned null task.
- Browser correction from pothole to deep pothole refreshed the queue/version and showed P1, 240 minutes and review history. A 390-pixel viewport had no horizontal overflow.
- Integration used an isolated test database, synthetic PNG and explicit demo detection. Normal project data was unchanged; no real model ran and this is not vision acceptance. Temporary Python was 3.12; full Python 3.11 backend acceptance was not claimed.
- Build succeeded with the existing >500 kB chunk warning (about 525 kB, gzip 148 kB); future route splitting remains possible.

## Delivery and next steps

Added ReviewPage, shared InspectionImage, review tests and a fixture exporter; updated navigation, styles and docs. At this stage, steps 2–5 remained on local feature/c-frontend-foundation without commit/push; A/B files were unchanged.

Step 6 task management was next; this stage did not implement task editing, maps, crews or assistant features early.
