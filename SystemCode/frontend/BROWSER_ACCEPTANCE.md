# Steps 7–8 restoration and browser acceptance

2026-10-17: The cumulative patch was applied to the original groupwork1 project. Steps 2–8 were on local feature/c-frontend-foundation, uncommitted/unpushed at this stage. Do not apply the old patch again.

Original-project lint, 100 tests in eight files and production build passed. JS 670.51 kB, gzip 179.93 kB; >500 kB warning retained.

Browser checks connected original Vite/FastAPI with isolated frontend-check.sqlite3, synthetic inspections and simulated matrices:

- Disable crew-01: record revision 1→2 and input revision 5→6. Explicit recalculation returned same-run GA/Greedy plans assigning all five tasks to the remaining three crews.
- Selecting a crew and stop 2 synchronised map selection, repair duration, arrival/completion and task link.
- At 390×844, document width was 375 ≤ 390. Map included Jurong and NUS-ISS; controls wrapped correctly. Focus and full-area reset worked.
- Restore crew-01: input revision 7. Old map/plans visibly became stale; recalculation produced new plans and algorithm switching worked.
- Default viewport restored; all test crews available.

Final test plans: GA plan-313e2b682ae7447ab83b176acf463bb3; Greedy plan-e1a65a69915f4d558c4d3b72f69fb32f; revision 7. These exist only in the isolated database and are not algorithm evaluation evidence.

No real model/Google/GPT calls or A/B source/ordinary-database changes. Step 6 task-submission browser acceptance was not repeated; automated tests passed. Step 9 same-run comparison followed.

## Step 9 addendum

2026-10-17: Same-run comparison, loss of evidence after refresh, explicit failure/recovery and desktop/mobile layout passed. See COMPARISON_GUIDE.md for full steps and final plans. Step 9 is complete; step 10 knowledge retrieval follows.
