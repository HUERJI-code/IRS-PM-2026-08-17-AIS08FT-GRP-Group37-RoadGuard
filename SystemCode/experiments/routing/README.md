# B routing experiments: four-crew GA versus Greedy

Owner: B. Design references: [experiments/README.md](../README.md) and [routing module guide](../../backend/roadguard/routing/README.md).

## Design

| Item | Value |
| --- | --- |
| Scenario | Four available crews; shared NUS-ISS depot; return to depot; 480-minute daily limit per crew (demo assumption pending A confirmation) |
| Tasks | 10/15/20 prefix-related tasks from [fixed fixtures](../../contracts/planning/README.md), `planning-synthetic-v2`; all `due_at=null` |
| Travel | `simulated_haversine_v1` matrix; GA/Greedy share one matrix per scenario, with SHA-256 recorded |
| Start | `2026-10-15T01:00:00Z` (09:00 Singapore) |
| Greedy | One deterministic run per scenario |
| GA | One run each for seeds 1-10; parameters from `routing.example.json`, without Greedy initialization |
| Comparison | Lexicographic `(unassigned P1, unassigned P2, unassigned P3, objective)`, matching optimization order; also report unassigned counts per priority, makespan, total travel, workload standard deviation, priority-weighted completion time and runtime |

Every run enters `raw_runs.csv`, including seeds where GA underperforms Greedy. `ga_convergence.csv` records generation-best values; `summary.json` gives statistics; `run_metadata.json` records full configuration/hash, fixture hashes, code commit, Python and platform.

## Reproduction

Run from repository root. Existing output directories are rejected:

```powershell
python SystemCode/experiments/routing/run_experiments.py --output-dir SystemCode/experiments/routing/results/<new-directory>
# Optional: requires local matplotlib, outside backend CI dependencies
python SystemCode/experiments/routing/plot_results.py SystemCode/experiments/routing/results/<new-directory>
```

Identical configuration and seed reproduce all metrics except `algorithm_runtime_ms` and `matrix_preparation_ms` (tested).

## Saved results

Four experiments ran on 2026-10-15: simulated matrices (code `7651947`) and Google matrices (code `06cb76b`), each with 480-minute and unlimited shifts. See [results/README.md](results/README.md) for raw data, matrices, figures and conclusions.

`--matrix-provider google_routes` calls the paid Google API (one 21x21 request at default task counts). `--unlimited-shift` removes shift capacity for sensitivity comparison. Both appear in `run_metadata.json`. Keep the worktree clean before running, including uncommitted older result directories, or metadata records `working_tree_dirty=true`.

`diagnose_tight_capacity.py` reproduces and diagnoses pure-GA omissions with Google matrix, 480-minute shifts and 15 tasks, reading saved matrices and printing results only. See [results/README.md](results/README.md), section 6.6.

## GA evaluation: ablation and gap to best-known solution

`evaluate_ga.py` evaluates GA itself, beyond whether it beats Greedy. It reads B6 saved matrices, checking hashes/node order without Google requests, and compares 12 scenarios: 2 matrices x 2 shift settings x 10/15/20 tasks:

- `greedy`: baseline;
- `ga_pure`: experimental GA, seeds 1-10;
- `ga_seeded`: online GA with Greedy in its initial population, seeds 1-10;
- `long_run`: larger budget (population 150, at most 1000 generations, patience 300), seeds 101-120, alternating pure/Greedy-initialized GA, used only to find a best-known solution (BKS).

BKS is the best observed plan and **is not guaranteed optimal**. Compute objective gaps only for runs assigning as many tasks as BKS; fewer assignments are separately marked `fewer_tasks_than_bks`.

```powershell
python SystemCode/experiments/routing/evaluate_ga.py --output-dir SystemCode/experiments/routing/results/ga-evaluation-v1
```

Approximately 6-7 minutes on one machine. Outputs: `raw_runs.csv`, `summary.json`, `best_known.json` including BKS routes, and `run_metadata.json`. Formal results/analysis: [results/README.md](results/README.md), section 7.

## Limitations

- Simulated travel cannot establish real-road time or cost savings.
- Runtime is local wall-clock time, separate from external API waiting (none for simulated matrices).
- Without deadlines, lateness is not reported; priority-weighted completion is not lateness.
- Objective weights/GA parameters are demo proposals, without independent-data tuning.
