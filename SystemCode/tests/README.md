# Shared backend and contract tests

Run `python -m pytest SystemCode/tests -q` from the repository root after installing the backend CI dependencies. Tests cover contracts, backend foundations, simulated rules, uploaded images, geographic validation and persisted inspection/review/task behavior. Remaining whole-system cases must cover:

- Accepted inspection -> priority rule -> active task -> four-crew replan.
- The implemented review/task flow connected to B's planner and C's frontend.
- Each assigned task occurs once; infeasible tasks are visible.
- GA and greedy obey the same constraints.
- Travel from the specified NUS-ISS depot outside the task area; origin-to-first-task travel must be counted.
- External-service failures and explicit demo-mode selection, without silent fallback.

These tests do not claim an implemented inspection-to-route workflow or model accuracy.

`test_vision.py`, `test_rules.py` and `test_demo_api.py` cover the explicit step 5 simulation, eight-class demo rules, threshold/selection boundaries and HTTP previews that do not mutate the task queue or input revision.

Step 6 adds `test_images.py`, `test_geography.py`, `test_workflow.py` and `test_workflow_api.py`. They exercise real decoding and EXIF normalization, bounded multipart uploads, polygon edges/holes/union, declared road scope, audit preservation, task state, idempotency and concurrent writes, optimistic versions, transactional rollback, frozen policies, schema migration and restart persistence. Inputs are generated locally; no external API or model weights are required. The real symlink test may skip on Windows accounts without permission; the Linux CI run exercises it.

## CI integration

RoadGuard CI runs Python application tests here once Python implementation is added. Group tests by module, use pytest discovery names, and declare the required test dependencies in `SystemCode/backend/requirements-ci.txt`. Frontend tests live with the frontend and run through its `test:ci` script. See [the shared CI guide](../../Miscellaneous/GITHUB_WORKFLOW.md) for exact commands and requirements.
