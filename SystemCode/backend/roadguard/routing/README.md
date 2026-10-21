# B routing module: four crews, simulated travel, Greedy and GA

Owner: B. Implementation milestone: 2026-10-15; documentation status updated: 2026-10-20. B-1 through B-5 and B6 cover the pure algorithm core, custom GA, experiments, database tables, crew/planning services, HTTP APIs and optional Google Routes matrix (section 10). Online service still defaults to simulated matrices. B6 compares GA/Greedy for 10/15/20 tasks with simulated and Google matrices (section 12). Online GA starts from Greedy to preserve a result no worse under the shared evaluator; experiments retain pure GA (section 13). The final report is available; video submission remains pending. The [RAG knowledge package](../../knowledge/README.md) now explains GA, saved-plan provenance and recorded experiments; assistant retrieval/generation is still unimplemented.

## 1. Demo assumptions: centralized configuration

[routing.example.json](../../../config/routing.example.json), version `b-routing-demo-v1`, `is_demo=true`. B selected these **demo assumptions pending A confirmation** on 2026-10-14; they are not approved operational rules:

| Item | Value | Notes |
| --- | --- | --- |
| Return to depot | `return_to_depot: true` | Travel from final task back to NUS-ISS counts toward travel/completion. A's `project.example.json` remains `null` (undecided); this module neither reads that null nor interprets it as false. |
| Shift | `shift_limit: {"mode": "limited", "minutes": 480}` | B set a 480-minute daily limit per crew on 2026-10-14, including travel/depot legs and service. `"unlimited"` explicitly removes capacity and differs from unknown. With four crews, some P2/P3 tasks among 15/20 exceed capacity and are marked `exceeds_shift_limit`. |
| Start | Every available crew leaves NUS-ISS at `planning_start_at` (minute 0) | First-version semantics replan from one common start, without tracking in-transit vehicles. |
| Waiting | No time windows; travel/service are continuous | `due_at` computes lateness only, not time windows. |
| Simulated matrix | Great-circle distance x 1.3 detour factor / 30 km/h, one decimal | `provider=simulated_haversine_v1`, `is_simulated=true`; neither road-network nor Google data. |
| Matrix source | `travel_matrix_provider: "simulated"` (default) | Optional `google_routes`, section 10; no automatic fallback. |

## 2. Data models (`b-*-v1-draft`, not yet in the shared contract)

Definitions: [models.py](models.py). HTTP endpoints are registered in the [API contract](../../../../Miscellaneous/API_CONTRACT.md); version names retain `-draft` until three-member integration confirmation.

- **PlanningInput**: `input_revision`, `planning_start_at`, `depot`, `crews` (all configured crews, including unavailable), `tasks` (a-task-query-v1 Task), `settings`. Tasks must be active with unique IDs.
- **TravelMatrix**: `node_ids[0]` is depot, followed by snapshot task order. `duration_minutes[i][j]` is i->j travel, without assumed symmetry; `null` means unreachable. Diagonal entries must be 0.
- **RoutePlan**：`plan_id`、`algorithm`（`ga`/`greedy`）、`crew_routes`、`unassigned_tasks`、`metrics`、`matrix_provider`、`matrix_is_simulated`、`settings`、`random_seed`、`algorithm_parameters`、`is_stale`、`is_demo=true`。
- **CrewRoute**: one entry per configured crew, `assigned`, `idle` or `unavailable`. `stops` follow visit order, with arrival/completion minutes relative to start. Also includes `travel_minutes` including depot legs, `return_travel_minutes` (null without return), `service_minutes`, `total_work_minutes`. `geometry=null`; frontend may show only **explicitly illustrative straight lines**.
- **Unassigned reasons**: `unknown_service_minutes`, `unreachable_from_depot`, `unreachable_to_depot`, `no_available_crew`, `exceeds_shift_limit`, `no_feasible_route_position`.

After `plan_routes()`, `check_plan_covers_input()` asserts every input task appears exactly once, either on a route or in unassigned_tasks.

## 3. Shared evaluator and objective

Greedy and GA share `RoutingProblem.evaluate()` in [evaluation.py](evaluation.py), keeping constraints and metric definitions identical:

1. **Prefilter** (same for both): unknown duration, unreachable depot departure, unreachable required return, no available crew, or a single task exceeding shift. These go directly to unassigned.
2. **Decode**: process each crew sequence. Skip and record tasks unreachable from the preceding point or exceeding shift including return; never silently drop them.
3. **Metrics**: total travel including first/return legs, total service, makespan (latest available-crew finish), workload standard deviation (travel+service for available crews, idle=0, unavailable excluded), priority-weighted mean completion (P1/P2/P3 weights 3/2/1). Lateness uses only tasks with `due_at`; all-null deadlines yield null lateness, never invented values.
4. **Objective** (`b-objective-v1`, demo weights pending A review): lexicographic `(unassigned P1 count, unassigned P2 count, unassigned P3 count, weighted cost)`. Cost = 1.0 x makespan + 0.2 x total travel + 0.5 x workload standard deviation + 0.5 x priority-weighted completion, all minutes. The first three entries prevent improving metrics by dropping tasks or sacrificing urgent tasks to fit more short ones. An earlier total-unassigned-only objective made shift-limited GA drop all 240-minute P1 tasks; regression tests cover the fix. Genuine capacity shortages (e.g. three crews cannot finish four P1 tasks within 480 minutes) still leave P1 unassigned with reasons. **Priority-weighted completion is not lateness**; without deadlines it approximates completing urgent tasks earlier.

## 4. Greedy baseline ([greedy.py](greedy.py))

Select the earliest-free available crew. Among its feasible remaining tasks choose highest priority (P1 > P2 > P3), then shortest travel from current location, then snapshot order. Stop a crew when no feasible tasks remain. The evaluator gives specific reasons for remaining tasks. Results are deterministic, without a random seed.

## 5. Custom GA ([ga.py](ga.py))

- **Chromosome**: `order` (schedulable-task permutation) plus `owner[task]` (available crew index). Crews visit their tasks in order. Owners come only from available crews; encoding itself prevents unavailable assignments and duplicate tasks.
- **Operators**: tournament selection k=3; OX crossover for `order`, uniform crossover for `owner`; mutation randomly chooses swap, segment reversal, crew reassignment or relocation.
- **Elitism**: 2. **Stop**: 300 generations or 80 without improvement. Population 60, crossover rate 0.9, mutation rate 0.3.
- **Reproducibility**: one `random.Random(seed)` supplies all randomness; default experiment seeds are 1-10.
- `ga.seed_with_greedy=false`: experimental populations omit Greedy to avoid favoring GA comparisons. Enabling it guarantees GA is no worse (tested), but that guarantee is not evidence of algorithm superiority.
- Online recalculation separately reads `planning_service.seed_with_greedy=true`; section 13.

## 6. Usage

```python
from roadguard.config import load_settings
from roadguard.routing import (build_planning_input, default_crews, depot_from_project,
                               load_routing_config, plan_routes, simulated_travel_matrix)

config = load_routing_config()
project = load_settings().project
planning_input = build_planning_input(snapshot, default_crews(project), depot_from_project(project),
                                      config.settings, "2026-10-15T01:00:00Z")
matrix = simulated_travel_matrix(planning_input, config.simulated_matrix)
greedy_plan, _ = plan_routes(planning_input, matrix, "greedy")
ga_plan, ga_result = plan_routes(planning_input, matrix, "ga", ga_parameters=config.ga, random_seed=1)
```

`snapshot` may be `TaskQueryService.snapshot()` output or a fixed `TaskSnapshot`. Online services follow the [handoff](../../../../Miscellaneous/BC_HANDOFF.md), section 9 below.

See [experiments/routing](../../../experiments/routing/README.md) for scripts, execution and output; [results/README.md](../../../experiments/routing/results/README.md) for B6 formal results/analysis.

## 7. Tests

```powershell
python -m pytest SystemCode/tests/test_routing_core.py SystemCode/tests/test_routing_ga.py SystemCode/tests/test_routing_experiments.py -q
```

Coverage: configuration/validation; matrix shape/node order; empty input; single-task round trip; no return; fewer tasks than crews; one/all crews unavailable; unknown duration; unreachable first/return/intertask legs; 480-minute limits; complete unlimited assignment; P1 preservation; deterministic/P1-first Greedy; exact 10/15/20 coverage; lateness; seeded GA reproducibility; monotonic elitism; shared constraints; legal operators; experiment output and overwrite rejection.

## 8. Known limitations and next steps

- Simulated matrices establish algorithm performance only on simulated travel, not real roads. Google matrices had a three-task smoke test and B6 experiments (two fetches, 882 elements total). Preliminary NUS-ISS entrance checks showed no anomaly but are not formal verification; confirm costs before expanded use.
- Fixed task points passed polygon validation only; work-eligible road placement is unverified.
- Return policy, shifts, objective weights and GA parameters are demo assumptions requiring A confirmation for formal use.
- B-4 changed A's shared `database.py` (v3 migration), `api/__init__.py` (registration), `main.py` (service assembly), plus hardcoded v2/endpoint-list assertions in `test_backend.py` and `test_workflow.py`.

## 9. B-4: persistence and HTTP APIs

See B's section in the [API contract](../../../../Miscellaneous/API_CONTRACT.md) or the Crews/Route plans groups in running `/docs`.

**Database (schema v3)**: `Database.initialize()` migrates v2 in place, adding `crews` (modified states only) and `route_plans` (plan JSON, algorithm, revision, creation time). Existing inspections/tasks/idempotency/input_revision remain unchanged. Missing v3 routing tables fail startup without rebuilding.

**Crews ([crews/](../crews/service.py))**: project `crew_ids` defines the roster. Unstored crews use defaults (available, `record_version=1`, `updated_at=null`) without startup writes. `PATCH` persists actual availability changes only, incrementing `input_revision` in the same transaction. Idempotency reuses A's `operation_keys`, scope `crew:<id>`.

**Recalculation ([service.py](service.py))**:
1. Read task snapshot and crew states in one read-only transaction, checking `expected_revision`.
2. Outside the transaction, build a matrix and run Greedy/GA on identical input (`planning_service.ga_seed=1`; Greedy-initialized GA, section 13).
3. Recheck revision in a write transaction and save both plans together. A changed revision saves neither and returns 409.

**Staleness**: compare saved `input_revision` with current on read; mismatch sets `is_stale=true`. Older plans remain queryable by ID for comparisons.

**Current orchestration (2026-10-21)**: accepted uploads and review confirmation/correction call the shared PlanningService after task commit. The paired GA/Greedy attempt uses the same snapshot and matrix and honors persistent crew constraints. Completion, cancellation, crew changes and assistant confirmations retain explicit recalculation. A planning failure does not roll back a saved task.

Tests: `SystemCode/tests/test_routing_api.py`: default crews without writes, changes/idempotency, conflicts, no-plan 404, empty queue, full create-task -> recalculate -> deactivate-crew -> stale -> complete-task -> recalculate flow, input changes during calculation preventing save, restart persistence, v2->v3 migration and malformed-database startup rejection.

## 10. B-5: Google Routes travel matrix

Implementation: [google_matrix.py](google_matrix.py); configuration: `google_routes` in [routing.example.json](../../../config/routing.example.json).

**Enable** (off by default, no charges while disabled):

```powershell
$env:ROADGUARD_TRAVEL_MATRIX_PROVIDER = "google_routes"
$env:ROADGUARD_GOOGLE_MAPS_API_KEY = "<server-side Routes API key>"
python -m uvicorn roadguard.main:app --app-dir SystemCode/backend
```

Alternatively change `travel_matrix_provider` in configuration; environment variables take precedence. Read the key only from `api_key_env`, never configuration, plans, logs, errors or frontend. Restrict it to Routes API in Google Cloud.

**Request**: `POST https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix`, `travelMode=DRIVE`, coordinates in `latLng`, field mask `originIndex,destinationIndex,duration,condition,status`.

| Rule | Implementation |
| --- | --- |
| Row/column order | Depot + snapshot task order. Map returned originIndex/destinationIndex to row i/column j; response order is arbitrary and symmetry is not assumed. proto3 omitted zero indices mean 0. |
| Units | Divide `duration` (e.g. `"754s"`) by 60, round to `minutes_decimals`; diagonal fixed 0. |
| Unreachable | `ROUTE_NOT_FOUND` becomes `null`; evaluator supplies `unreachable_*` and other reasons, never zero minutes. |
| Failure | Missing keys, HTTP/timeout/network errors, nonzero element status, missing/duplicate elements or malformed data raise `TravelMatrixError`. Recalculation returns 503 `travel_matrix_unavailable`, saves neither plan and **never falls back to simulated matrices**. |
| Chunking | At most 25x25 and `max_elements_per_request` (<=625; `TRAFFIC_AWARE_OPTIMAL` limit 100). 20 tasks + depot = 21x21 = 441 elements in one request. |
| Cost protection | Above `max_nodes` (default 31, or 30 tasks), reject without requesting. Uncached fetch bills node_count squared elements, recorded in `parameters.billed_elements_per_fetch`. |
| Cache | `TRAFFIC_UNAWARE` only: in-process coordinate/parameter cache (default 16) avoids charges after crew-only changes. Hits retain original `generated_at` and set `served_from_cache=true`. Restart clears it. |
| Departure | Default `TRAFFIC_UNAWARE` sends none. Traffic-aware modes send future `planning_start_at` as `departureTime`; past times make Google use request time. Actual value: `parameters.departure_time`. |
| GA/Greedy consistency | One matrix fetch per recalculation, shared by both. `RecalculationResult`/RoutePlan identify `matrix_provider`, `matrix_is_simulated=false` and `matrix_generated_at`. |

**Pending / integration needs**:

- **Smoke test (2026-10-15, B's local real key, `TRAFFIC_UNAWARE`)**: [google_smoke.py](../../../experiments/routing/google_smoke.py) created three Jurong demo tasks, 16 elements. Result: `matrix_is_simulated=false`; outbound/return depot pairs 20.3/21.8, 20.9/18.8, 23.4/23.9 minutes, asymmetric and all reachable. Simulated results at the same locations were about 25-31 minutes, of similar magnitude. Greedy/GA both totaled 129.1 travel minutes. This three-point smoke test is not formal accuracy evaluation.
- NUS-ISS vehicle entrance: all three first legs are reachable with plausible times; preliminary checks show no anomaly, but entrance location is **not formally verified**. Google snaps coordinates to nearby roads. If first-leg anomalies arise, A/B must record entrance coordinates and update depot version; GA/Greedy retain shared coordinates.
- No road geometry: `geometry` stays null; C may show only explicitly illustrative straight lines.
- B6 completed Google-matrix 10/15/20-task experiments; [results/README.md](../../../experiments/routing/results/README.md), section 6.

Tests: `SystemCode/tests/test_routing_google_matrix.py`, all with fake transport and real-network blocking. Smoke testing exposed crew-order-dependent `sum()` totals (129.1 versus 129.10000000000002 for identical routes); `math.fsum` fixes this with regression coverage.

## 11. New files from B-1 through B6

Stages match tests: B-1 core/Greedy, B-2 GA, B-3 experiments, B-4 persistence/APIs, B-5 Google, B6 formal results.

| File | Stage | Purpose |
| --- | --- | --- |
| [routing/\_\_init\_\_.py](__init__.py) | B-1 | Public routing exports: models, matrices, planning functions and configuration loading |
| [routing/models.py](models.py) | B-1 | Crew, Depot, PlanningInput, TravelMatrix, RoutePlan, CrewRoute, Stop, unassigned reasons and validation |
| [routing/settings.py](settings.py) | B-1 | Load routing.example.json shifts, return policy, objective weights, GA parameters and matrix source; assemble PlanningInput |
| [routing/matrix.py](matrix.py) | B-1 | Simulated matrix: great-circle distance x detour factor / speed; depot first, then snapshot task order |
| [routing/evaluation.py](evaluation.py) | B-1 | Shared Greedy/GA constraint checks, route decoding, metrics and objective evaluation |
| [routing/greedy.py](greedy.py) | B-1 | Greedy baseline: earliest-free crew selects most urgent, nearest task |
| [routing/planner.py](planner.py) | B-1 | Stateless plan_routes(): one input + one matrix -> validated RoutePlan, with exact task coverage |
| [routing/ga.py](ga.py) | B-2 | Custom GA: order/owner chromosomes, OX crossover, four mutations, elitism and seeded reproduction |
| [config/routing.example.json](../../../config/routing.example.json) | B-1 | Central demo configuration; B-5 adds travel_matrix_provider and google_routes |
| [experiments/routing/run_experiments.py](../../../experiments/routing/run_experiments.py) | B-3 (B6 extension) | Multi-seed GA/Greedy comparison for 10/15/20 tasks; raw data, convergence, summaries, runtime metadata and full matrices; B6 adds --matrix-provider google_routes and --unlimited-shift |
| [experiments/routing/plot_results.py](../../../experiments/routing/plot_results.py) | B-3 (B6 extension) | Plot comparisons/convergence from saved results (matplotlib); B6 titles include matrix source and shifts |
| [experiments/routing/README.md](../../../experiments/routing/README.md) | B-3 | Experiment design and reproduction |
| [crews/\_\_init\_\_.py](../crews/__init__.py) | B-4 | Crew module entry |
| [crews/schemas.py](../crews/schemas.py) | B-4 | Crew request/response models (b-crew-v1) |
| [crews/service.py](../crews/service.py) | B-4 | Read/change availability with idempotency; increment input_revision in the same transaction |
| [crews/api.py](../crews/api.py) | B-4 | GET /crews and PATCH /crews/{id} |
| [routing/service.py](service.py) | B-4 | Read consistent snapshot -> fetch matrix -> Greedy/GA -> recheck revision in write transaction and save; plan queries/staleness |
| [routing/api.py](api.py) | B-4 | POST /route-plans/recalculate, GET /route-plans/latest, GET /route-plans/{id} |
| [routing/google_matrix.py](google_matrix.py) | B-5 | Google Routes matrix: chunking, index mapping, unreachable=null, errors without fallback, caching and cost protection |
| [experiments/routing/evaluate_ga.py](../../../experiments/routing/evaluate_ga.py) | B6 follow-up | Greedy/pure-GA/online-GA ablation and best-known gaps using saved matrices, no API calls; section 14 |
| [tests/test_routing_ga_evaluation.py](../../../tests/test_routing_ga_evaluation.py) | B6 follow-up | BKS no worse than any run, online GA no worse than Greedy, gaps only with equal coverage, tampered-matrix/overwrite rejection |
| `experiments/routing/results/ga-evaluation-v1/` | B6 follow-up | GA evaluation outputs: raw runs, summary, BKS routes and metadata |
| [experiments/routing/diagnose_tight_capacity.py](../../../experiments/routing/diagnose_tight_capacity.py) | B6 follow-up | Diagnose pure-GA omissions at tight capacity using saved Google matrices, no API calls/writes; section 13 |
| [experiments/routing/google_smoke.py](../../../experiments/routing/google_smoke.py) | B-5 | Google smoke test: create 3 demo tasks -> recalculate -> print provenance and leg durations |
| [tests/test_routing_core.py](../../../tests/test_routing_core.py) | B-1 | Model, simulated matrix, evaluator and Greedy boundaries |
| [tests/test_routing_ga.py](../../../tests/test_routing_ga.py) | B-2 | GA legality, reproducibility and shared Greedy constraints |
| [tests/test_routing_experiments.py](../../../tests/test_routing_experiments.py) | B-3 (B6 extension) | Artifact completeness/overwrite rejection; B6 matrix retention, one Google fetch plus slicing, no output on fetch failure, unlimited-shift records |
| [experiments/routing/results/README.md](../../../experiments/routing/results/README.md) | B6 | Report-ready experiment records, metric tables, figures, conclusions and limitations |
| `experiments/routing/results/simulated-shift480-v1/` / `simulated-unlimited-v1/` | B6 | Simulated 480-minute/unlimited outputs: raw data, convergence, summary, metadata, matrices and plots |
| `experiments/routing/results/google-shift480-v1/` / `google-unlimited-v1/` | B6 | Google matrix outputs with the same contents |
| [tests/test_routing_api.py](../../../tests/test_routing_api.py) | B-4 | Crew API, recalculation, conflicts, staleness, restart persistence and v2->v3 migration |
| [tests/test_routing_google_matrix.py](../../../tests/test_routing_google_matrix.py) | B-5 | Fake-transport Google mapping, chunking, caching, errors and no fallback |

B-4 also changed A's existing `database.py` (v3 migration), `api/__init__.py` (registration) and `main.py` (assembly), omitted from this new-file table.

## 12. B6: routing metrics and experiments

Results/analysis: [results/README.md](../../../experiments/routing/results/README.md). Design/reproduction: [experiments/routing](../../../experiments/routing/README.md).

| Experiment | Code | Content |
| --- | --- | --- |
| `simulated-shift480-v1` | `7651947` | Simulated matrix, 480-minute shifts (main) |
| `simulated-unlimited-v1` | `7651947` | Simulated matrix, unlimited shifts (sensitivity) |
| `google-shift480-v1` | `06cb76b` | Google matrix, 480-minute shifts |
| `google-unlimited-v1` | `06cb76b` | Google matrix, unlimited shifts |

Shared conditions: four crews, 10/15/20 tasks, one Greedy run and GA seeds 1-10. GA/Greedy share input/matrix per scenario. Algorithm runtime is separate from matrix preparation (Google API waiting). Every run retains full matrix and code version.

Main conclusions (results sections 4 and 6.4):

- At 480-minute shifts, capacity is the main bottleneck for 15/20 tasks; all P1 tasks are assigned.
- GA mainly completes urgent work earlier; on simulated matrices total travel is slightly higher.
- **GA is not always better**: with Google, 480-minute shifts and 15 tasks, 5/10 seeds assign one fewer P3 than Greedy. These results are preserved unchanged.
- Source affects conclusions: in the same scenario Greedy misses three tasks with simulated travel and two with Google.

B6 extended experiment/plot scripts and tests only, without changing online services or APIs.

## 13. Online GA starts from Greedy: post-B6 improvement

**Problem**: pure GA assigned one fewer P3 than Greedy in 5/10 seeds for Google/480-minute/15-task B6 input. [diagnose_tight_capacity.py](../../../experiments/routing/diagnose_tight_capacity.py) found the following ([results section 6.6](../../../experiments/routing/results/README.md)):

- Service totals exactly 4x480 minutes for 15 tasks; travel reduces maximum coverage to 13, a tight packing problem.
- Failed seeds lock into 12 assignments in generations 1-10. Remaining capacity concentrates in one crew (60-79 minutes), insufficient for P3 service 60 plus round trip; no direct insertion is feasible. One more assignment requires coordinated relocation of an existing task followed by insertion, while each mutation performs one action.
- Raising patience to 300 and generations to 1000 leaves the same five failed seeds. Population/mutation-rate changes only change which seeds fail. This is a structural search issue, so parameter tuning was not pursued.

**Approach**: use separate settings for online result quality and fair experimental comparisons.

| Scenario | Setting | Effect |
| --- | --- | --- |
| Online `POST /route-plans/recalculate` | `planning_service.seed_with_greedy=true`: initial population contains Greedy | Elitism guarantees no worse `(unassigned P1, P2, P3, objective)`. All 10/10 seeds assign 13 tasks here, objective 668.2-670.4 versus Greedy 682.9. |
| `run_experiments.py` | Retains `ga.seed_with_greedy=false` | Independent pure-GA/Greedy comparison; B6 results unchanged. |

- Saved RoutePlan `algorithm_parameters.seed_with_greedy` records actual settings, allowing reports/frontend to describe online GA as GA + Greedy initialization.
- API fields, database and frontend are unchanged; online GA still returns an independent `algorithm="ga"` plan.
- Tests: `test_routing_ga.py` replays saved matrices (pure seed 2 misses a task; all 10 seeded runs are no worse than Greedy). `test_routing_api.py` checks recorded settings and no-worse online plans; `test_routing_core.py` verifies both configuration values.
- Optional future improvement: relocation+insertion repair (memetic GA). Diagnostics repair three of five failed seeds; not implemented.

## 14. GA evaluation: ablation and best-known-solution gap

Since Greedy-initialized online GA cannot be worse, merely beating Greedy is insufficient evaluation. [evaluate_ga.py](../../../experiments/routing/evaluate_ga.py) compares Greedy, pure GA and online GA across 12 scenarios (simulated/Google x 480-minute/unlimited x 10/15/20 tasks), with larger-budget BKS reference runs. Outputs: `ga-evaluation-v1`, code `7bb1536`; full analysis in [results section 7](../../../experiments/routing/results/README.md).

| Evaluation | Result |
| --- | --- |
| BKS gap | Greedy 1.2%-5.1%; online GA 0.2%-1.8%, reducing Greedy's gap 63%-89% |
| Versus Greedy | Online GA improves 120/120 runs, mean objectives 0.7%-3.6% lower, never fewer assignments |
| Ablation: Greedy initialization | Online GA closer to BKS at 10/15 tasks; some 20-task scenarios tie or favor pure GA slightly. Pure GA loses coverage in 5/10 tight-capacity runs; online GA never does. |
| Stability | Online seed variation lower than pure GA in 8/12 scenarios |
| Speed | Defaults 0.1-0.4 seconds; about 10x budget (0.7-5.4 seconds) averages within +/-0.8% of online GA |

Limitations: BKS is not guaranteed optimal and gaps are lower-bound estimates; one synthetic task set and B6's two matrices; ten seeds without significance testing.
