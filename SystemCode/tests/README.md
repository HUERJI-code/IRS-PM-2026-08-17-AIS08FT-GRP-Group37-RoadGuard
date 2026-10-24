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

Step 7 adds `test_task_query.py` and `test_task_query_api.py` for complete shared-revision snapshots (including 125 tasks), nullable fields, corruption failures, caller-owned connections and concurrent updates. `test_planning_fixtures.py` checks deterministic inputs against central sources; `test_knowledge_handoff.py` checks knowledge citations/versions and source integrity. `test_handoff_demo.py` runs the shipped HTTP consumer example against isolated handlers; it creates real persisted demo records, not fake success responses.

B's routing work adds `test_routing_core.py`, `test_routing_ga.py` and `test_routing_experiments.py`. They cover the shared evaluator, simulated matrix, Greedy and GA on fixed snapshots: empty/single/fewer-than-four tasks, disabled crews, unreachable legs, unknown service time, shift limits, exactly-once coverage, fixed seeds and experiment provenance. They use simulated travel times and no database; `test_routing_api.py` covers B-4: persisted crew availability, idempotent crew changes, recalculation with revision checks, stale plans, plan queries, restart persistence and the v2→v3 migration. `test_routing_google_matrix.py` covers B-5 with a fake transport (real network calls are blocked): index mapping, asymmetry, unreachable as null, request blocking within element caps, cache, departure time, missing key, malformed/partial responses, HTTP/timeout mapping, and recalculation that saves nothing and never falls back on failure. See the [routing module guide](../backend/roadguard/routing/README.md).

## CI integration

Step 8 adds dataset archive/content/group-split tests, resumable download tests, checkpoint/evaluation/cache-cleanup tests and real-detector adapter/workflow tests. Ordinary CI uses generated small files and injected models, requires no GPU or optional vision packages, and never downloads or trains. Actual GPU recovery, full-data evaluation and real HTTP evidence are recorded separately in the [Step 8 acceptance report](../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md).

The 30-epoch follow-up adds `test_error_analysis.py`, `test_vision_comparison.py`, `test_cpu_benchmark.py` and actual-batch guards in `test_vision_training.py`. These check matching/counting, frozen run evidence, model selection, CPU timing input/precision boundaries and rejected batch shrinkage using lightweight fixtures. They do not substitute for the [actual paired training, CPU and HTTP acceptance](../../Miscellaneous/VISION_30_EPOCH_COMPARISON.md).

The balanced-metrics follow-up adds `test_balanced_metrics.py` for confidence-prefix matching equivalence, duplicates and subtype mistakes, primary/diagnostic separation, undefined per-class scores, deterministic threshold selection, real export provenance and rejected partial or altered inputs. Training configuration tests enforce integer bounds and stride-aligned image sizes up to 960; the runner ceiling is 60 epochs, while the frozen experiment actually ran 40. Local application regression: 761 passed, one Windows symlink-permission skip. These lightweight checks are separate from the [actual 40-epoch training, numerical checks and 11-case real HTTP acceptance](../../Miscellaneous/BALANCED_VISION_OPTIMIZATION.md); passing software tests does not establish the 70% model-quality target.

RoadGuard CI runs Python application tests here once Python implementation is added. Group tests by module, use pytest discovery names, and declare the required test dependencies in `SystemCode/backend/requirements-ci.txt`. Frontend tests live with the frontend and run through its `test:ci` script. See [the shared CI guide](../docs/PROJECT_BASELINE.md) for exact commands and requirements.
