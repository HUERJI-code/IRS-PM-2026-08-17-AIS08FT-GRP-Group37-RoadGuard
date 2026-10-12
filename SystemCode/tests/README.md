# Integration tests - planned

Add tests when the corresponding behavior exists. The first integration cases should cover:

- Accepted inspection -> priority rule -> active task -> four-crew replan.
- Uncertain inspection -> review -> confirm/correct/dismiss.
- Each assigned task occurs once; infeasible tasks are visible.
- GA and greedy obey the same constraints.
- Study-area validation after the Jurong boundary is agreed.
- External-service failure and explicitly labelled demonstration fallback.

There are no runnable application tests in this scaffold yet.

## CI integration

RoadGuard CI runs Python application tests here once Python implementation is added. Group tests by module, use pytest discovery names, and declare the required test dependencies in `SystemCode/backend/requirements-ci.txt`. Frontend tests live with the frontend and run through its `test:ci` script. See [the shared CI guide](../../Miscellaneous/GITHUB_WORKFLOW.md) for exact commands and requirements.
