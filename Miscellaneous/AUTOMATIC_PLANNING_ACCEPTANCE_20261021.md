# Automatic planning acceptance 2026-10-21

Owner authorization: automatically update routes after a new accepted inspection task, including review confirmation/correction. Existing completion, cancellation, crew and assistant workflows keep explicit replanning.

Accepted inspection uploads and review confirmation/correction automatically attempt paired GA/Greedy planning after the task transaction commits. Both algorithms share one task/crew snapshot and travel matrix and retain durable crew constraints. Pending review, no detection and dismissal trigger no planning. Completion, cancellation, crew changes and assistant confirmations still require explicit replanning.

The synchronous HTTP response waits for the attempt. The upload JSON retains exactly inspection_id, status, detection and task_id; X-RoadGuard-Replanning reports completed, failed or not_needed. An accepted idempotent replay repairs missing or stale plans and skips calculation when both latest plans are current. One process serializes automatic attempts and permits at most three total attempts (two retries), retrying stale-input conflicts only. A failure preserves the committed task and previous plans, which remain stale; the interface warns and retains manual recalculation. There is no durable worker or automatic restart recovery: a crash after task commit requires accepted replay or manual retry.

## Focused acceptance

The primary agent reviewed the implementation and isolated acceptance results. Routing tests use the real shared GA/Greedy services with simulated travel matrices; real-mode detection uses an explicit detector double. No paid Google/GPT call or model training was performed.

| Check | Required evidence | Result |
| --- | --- | --- |
| Accepted real/demo upload and review confirmation/correction | Task committed before paired current plans; constraints retained through an actual task-move preview/confirmation and new upload | Passed |
| Pending review, no detection and dismissal | No automatic planning | Passed |
| Replay | No duplicate task; recover missing/stale pairs; skip current pair and completed-task replay | Passed |
| Failure and conflict | Upload/review failures retain tasks; old plans remain stale; concurrent acceptance and bounded stale-only retries cannot save superseded plans | Passed |
| HTTP and frontend | Four upload fields unchanged; header outcomes; warning and manual retry retained; one browser write per action | Passed |
| Regression | Existing workflow, authentication, routing and assistant task-change suites | Passed |

Local verification:

- `test_automatic_planning.py`: 15 passed, including actual shared planning, concurrency, recovery and persistent crew constraints.
- Existing workflow/routing/single-box suites: 54 passed. Authentication and assistant task-change suites: 27 passed. These counts describe separate focused runs, not an added overall coverage score.
- Google matrix suite: 22 passed with fake transport. Each accepted task's paired run shares one matrix acquisition; an immediate manual run reuses the latest traffic-unaware cache. No real Google call was made.
- Complete frontend suite: 185 passed; ESLint, TypeScript and production build passed. The existing bundle-size warning remains.
- Knowledge integrity: 74 passed against an isolated staged tree; OpenAPI snapshot consistency passed. Repository structure/link checks passed for 484 files; 49 CI guardrail tests passed.
- Cached E5/Chroma index rebuilt for `a-knowledge-v19` with 71 passages. Three local retrieval questions returned the updated acceptance, failure and completion-policy sources. This is retrieval evidence, not a new GPT answer-quality evaluation.
- Both Group37 final-report copies match; all 42 rendered pages were reviewed, including subsequent changed pages. Historical algorithm results and submitted-proposal content are preserved.

The GitHub PR CI remains the merge gate and runs the full declared Python and frontend checks. Automatic runs update saved routes; the comparison page still requires a matching recalculation response retained by the browser. Use the manual recalculation action when that receipt is absent. This change does not add live route updates to already-open browser pages.

Historical routing experiments and earlier acceptance counts are unchanged; this orchestration change is not a new algorithm-quality result.
