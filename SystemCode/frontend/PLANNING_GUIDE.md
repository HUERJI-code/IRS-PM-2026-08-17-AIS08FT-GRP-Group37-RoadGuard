# C step 7: Four-crew controls and explicit recalculation

2026-10-17; owner C. Restored to the original project with browser acceptance for crew changes, recalculation, stale status and map interactions; see BROWSER_ACCEPTANCE.md.

## Usage and behaviour

Open /routes. It reads all backend-configured crews and shows availability, depot and record revision without hardcoding crew count. Enable/Disable saves status only; click “Recalculate GA and Greedy” separately to generate plans.

The page reads crews first, then a complete active-task snapshot at the same input_revision. Mismatches require refresh. Upload results, review-linked tasks and task details share the recalculation entry. After crew changes, the returned revision is used to recheck the snapshot; recalculation explicitly carries expected_revision. Unaccepted, completed and cancelled tasks are excluded.

The response shows the same-run GA/Greedy IDs, revision, start time, task coverage and matrix source, then reads saved plans by ID. Idle/unavailable crews remain visible. Unassigned reasons come from the backend. Step 8 map is integrated (MAP_GUIDE.md); step 9 comparison is complete and linked from recalculation results (COMPARISON_GUIDE.md).

## Concurrency and failure

- Crew changes carry fixed request_id, expected_version and available. Unknown outcomes retry the same request; conflict requires rereading and a new chosen action.
- If input reads or recalculation fail after a successful crew save, retain the saved status without rollback/duplicate PATCH. Saved plans remain visible and are marked stale by backend is_stale and the read revision.
- Recalculation has no idempotency ID. Network/timeouts do not trigger automatic recalculation. Read inputs/saved plans first; latest plans cannot establish which request produced them. A checked “start a new calculation” acknowledgement is required before a potentially duplicate calculation.
- Successful recalculation followed by detail-read failure retains its response and retries reads, without misreporting calculation failure.
- Google matrix failure does not fall back to simulation. The frontend reports backend provenance; real Google was not used for acceptance.
- Recalculation waits up to 120 seconds. Leaving cancels frontend waiting, not necessarily backend work. Pending requests live in memory and cannot survive refresh/source changes.
- Missing plans, empty active snapshots and service failures remain distinct. Read-only mock mode blocks crew edits and recalculation.

## Files and endpoints

Added src/pages/RoutesPage.tsx, RoutesPage.test.tsx, src/test/planning-fixtures.json and scripts/export_planning_fixtures.py; updated App and upload/review/task entries. No new dependencies or A/B backend, shared-contract, algorithm or database-structure changes.

Uses GET /crews, PATCH /crews/{id}, GET /tasks/snapshot, POST /route-plans/recalculate, GET /route-plans/latest and GET /route-plans/{id}, all through the existing client with /api/v1 prefix.

## Validation

- Working copy ran lint, test:ci and build; final results below.
- Fifteen dispatch tests include StrictMode mount/cancel, revisions, original-request retries, duplicates, unknown-recalculation checks, empty tasks, read-only mock, failed plan reads, all crews unavailable and unassigned reasons.
- export_planning_fixtures.py uses real FastAPI TestClient/temporary SQLite to verify crew save/replay, stale 409, stale old plans, same-run dual plans and no_available_crew when all crews are disabled. Synthetic photos, demo detection and simulated matrices leave ordinary project data untouched.
- Backend checks used Python 3.12 and do not establish full Python 3.11 acceptance.
- Original-project browser/mobile checks completed. Build retains the >500 kB JS warning.

## Delivery

Code/docs restored to the original project; at this stage uncommitted/unpushed with no remote CI result. See BROWSER_ACCEPTANCE.md.

## Final checks

2026-10-16: lint, all 87 tests in seven files and production build passed in the writable copy. JS 546.97 kB, gzip 152.65 kB; size warning retained.
