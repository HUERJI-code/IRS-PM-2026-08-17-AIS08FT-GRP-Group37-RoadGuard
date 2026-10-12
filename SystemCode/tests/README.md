# Shared backend and contract tests

Run `python -m pytest SystemCode/tests -q` from the repository root after installing the backend CI dependencies. Current tests cover DTO validation and fixture consistency, configuration, health/error responses, SQLite persistence and shared input-revision transactions. Future end-to-end cases must cover:

- Accepted inspection -> priority rule -> active task -> four-crew replan.
- Uncertain inspection -> review -> confirm/correct/dismiss.
- Each assigned task occurs once; infeasible tasks are visible.
- GA and greedy obey the same constraints.
- Task membership in the JE/JW polygons, including edges; the specified NUS-ISS depot is permitted outside the task area, and origin-to-first-task travel is counted.
- External-service failure and explicitly labelled demonstration fallback.

These tests do not claim an implemented inspection-to-route workflow or model accuracy.

`test_vision.py`, `test_rules.py` and `test_demo_api.py` cover the explicit step 5 simulation, eight-class demo rules, threshold/selection boundaries and HTTP previews that do not mutate the task queue or input revision.

## CI integration

RoadGuard CI runs Python application tests here once Python implementation is added. Group tests by module, use pytest discovery names, and declare the required test dependencies in `SystemCode/backend/requirements-ci.txt`. Frontend tests live with the frontend and run through its `test:ci` script. See [the shared CI guide](../../Miscellaneous/GITHUB_WORKFLOW.md) for exact commands and requirements.
