# Fixed task snapshots: A -> B/C

This directory provides offline `a-task-query-v1` `TaskSnapshot` fixtures validated by `roadguard.schemas.task_query.TaskSnapshot`. Every item in `tasks` uses exactly the original public `Task` fields, without workflow history fields. These are synthetic development fixtures, not a live database, field tasks, road-verification results or completed experiments.

| File | Purpose |
| --- | --- |
| `tasks_10.json` / `tasks_15.json` / `tasks_20.json` | Fixed sets of 10/15/20 active demo tasks; 10 is a prefix of 15, and 15 of 20 |
| `tasks_empty.json` | Valid empty active-queue snapshot |
| `tasks_unknown_service.json` | Separate unknown-service-time contract boundary; `service_minutes=null` must not be treated as zero |
| `manifest.json` | Source SHA-256, geography/depot/label/rule versions, scenario configuration and fixture limitations |
| `generate.py` | Reproduces these six JSON files from shared sources without reading or creating a database |

All snapshots have `source=synthetic_fixture` and `is_demo=true`. `input_revision=0` is a fixed fixture marker, not the live database revision or task count. IDs, UTC timestamps and point order are fixed; every task is `active`. All `due_at=null`, so deadline lateness cannot be calculated from these fixtures.

Labels cycle through class_id in the canonical [label schema](../../model/label_schema.json). Severity, priority, duration and rule version come from [demo_rules.example.json](../../config/demo_rules.example.json), without a second mapping. Current `planning-synthetic-v2` uses `demo-rules-v2`: P3/P2/P1 = 60/120/240 minutes. The same task ID may have different content under different fixture_version values; record fixture versions and file digests in comparisons. These are finalized course-simulation assumptions; historical v1 fixtures remain available through Git. The unknown-service file explicitly sets one derived task's duration to null while retaining other shared-rule attributes. This separate contract boundary is not actual output of the current complete rule mapping and is excluded from the 10/15/20 sets.

Coordinates are synthesized on a fixed grid inside the frozen [JE/JW polygons](../../../Miscellaneous/geography/jurong-boundary-mp2025.geojson), with union coverage checked. **Road networks, road types and permissions have not been checked; points may be off-road or on excluded roads.** Use them for parsing, map loading and algorithm data-flow development. They cannot support real travel experiments or performance conclusions before road verification, travel matrices, constraint freezing and B's planner are complete.

Four crew IDs and NUS-ISS origin context come from [project configuration](../../config/project.example.json). The manifest records these without creating Crew models. The depot is permitted outside the task area; its vehicle entrance remains unverified. `shift_minutes` and return-to-depot policy remain unknown; null means neither unlimited shifts nor no return. This directory generates no matrices, routes, GA/Greedy results or experiment metrics.

Run from the repository root in the shared backend environment:

```powershell
python SystemCode/contracts/planning/generate.py
python SystemCode/contracts/planning/generate.py --check
python -m pytest SystemCode/tests/test_planning_fixtures.py -q
```

The generator resolves repository paths from its own source location; invoking its absolute path from another working directory produces the same content. By default it writes only the six explicit JSON files above. `--check` and tests generate and compare in memory without changing the checkout. Regenerate and inspect the manifest when source configuration changes; documentation edits cannot disguise changed fixtures. Do not initialize the application database from these files or return them as a successful fallback when online queries fail.
