# C step 9: Same-run GA / Greedy comparison

2026-10-17; owner C. Implemented directly in the original frontend, uncommitted/unpushed at this stage. No changes to A/B modules, shared APIs, database structure or dependencies.

## Usage

In `/routes`, check inputs, select “Recalculate GA and Greedy”, then “Compare this GA and Greedy run”. Navigation also opens `/comparison`. The page reads the saved plans using the two response IDs. “Reload comparison” issues GET only and never recalculates.

The response stays in the current application session across navigation. Full refresh, closure or source change clears it. Direct entry can show raw metrics from two latest plans but explicitly lacks same-run evidence and calculates no differences/percentages. Current APIs provide no queryable run/matrix identifier; matching revisions/timestamps are insufficient. Reliable historical comparison requires a persisted batch association from B.

## Checks and metrics

- Verify algorithms, plan IDs, response summaries, input revision, start, task/matrix provenance, complete task-ID sets/uniqueness, crews/availability, depot, planning configuration and weights. Object-key order is irrelevant. Read failure clears unverified presentation; retries issue no POST.
- A successful recalculation response supplies same-run evidence under the shared-input/matrix contract; independent latest plans do not. Current health input_revision and plan is_stale identify stale plans. Historical same-run comparisons remain valid but are not current dispatch instructions.
- Metrics include assigned/unassigned counts, unassigned P1/P2/P3, travel, repairs, makespan, workload standard deviation, priority-weighted mean completion, deadline count, lateness, objective and algorithm milliseconds.
- All metrics come from saved plans. Frontend calculates only display differences and `(GA - Greedy) / Greedy`, preserving sign. Zero baselines produce no percentage; null never becomes zero. Different assigned-task sets suppress time/objective differences and percentages to avoid claiming gains from scheduling fewer tasks.
- Without deadlines, lateness is not calculable. With deadlines, backend lateness includes assigned tasks only, so also inspect unassigned reasons. Weighted completion is not lateness; algorithm runtime excludes matrix/API waiting.
- Interpret the objective lexicographically by unassigned P1/P2/P3 then weighted cost. One reduction does not establish universal improvement or monetary savings. Preserve weights, settings, seed and algorithm parameters; seed_with_greedy true/false/missing separately states whether online GA used a Greedy initial solution.
- Each plan lists all crews, workloads and unassigned reasons. One online run is not a multi-seed experiment or proof that GA beats Greedy.

## Validation

Node 22 lint, test:ci and build passed in the original project: ten files, 127 tests, including 27 additions. Coverage includes checks above, evidence clearing on source changes, persistence across navigation, read failure/GET-only retry, StrictMode cancellation, empty tasks, all crews unavailable and zero/unknown values. JS 682.86 kB, gzip 183.90 kB; >500 kB warning retained.

Browser acceptance used the original project and isolated database with synthetic inspections/simulated matrices:

1. Direct comparison displayed raw latest values and “Comparability not verified”, without percentage conclusions.
2. Recalculation then comparison showed verified same-run evidence, five tasks, input revision 7, matching IDs/sources/metrics and GA with a Greedy seed.
3. Desktop 1280×900 table verified. At 390×844, document width 375 ≤ 390; the 540-pixel table scrolled locally. Default viewport restored afterwards.
4. Full refresh cleared evidence. Explicit mock failure showed errors and removed metrics. Returning live restored reads without old evidence.
5. Final explicit recalculation retained verified GA `plan-b7a5e2ba130049b6bc5e055d65c5c003` and Greedy `plan-a560795d1dcc4940891c6868b62fa141`, revision 7.

No real model, Google or GPT calls. Test plans are not algorithm experiment data. Automated tests cover version/settings/source mismatch. Step 6 task-submission browser acceptance was not repeated in this stage.

## Files and next step

Added `src/pages/ComparisonPage.tsx` and tests plus `src/planning/{comparison.ts,comparison.test.ts,runContext.ts,PlanningRunProvider.tsx}`; updated App, RoutesPage, integration tests and styles. Existing client/response validation retained, no new dependencies.

Step 9 is complete. Step 10 is knowledge cleaning, chunking and retrieval. Assistant/knowledge backend work was not implemented early.
