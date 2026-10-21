# C Step 13 historical local assistant cases

English display summary of the original record; no cases were rerun for this
translation. The lossless original README is in
[historical-readme-originals.json](../historical-readme-originals.json).

The 22 synthetic records contain ten route questions, eleven crew-change cases
and one cross-role HTTP workflow. Real GPT and Google calls were both zero.
The provider double selected preset evidence, testing plan IDs, citations,
versions, read-only behavior and refusal states. `model_called` records a call
to that abstraction; `real_model_called=false` records the absence of real calls.
These results cannot establish GPT accuracy or answer sufficiency.

Cases a01–a02 confirm disabling/enabling crew-02; a03 cancels; a04–a05 check replay
and concurrent confirmation with one mutation; a06–a07 reject stale previews
after task/crew changes; a08 checks a no-op; a09–a10 reject ambiguous or unsupported
instructions; a11 recovers after a failed replan while preserving crew state.

Questions q01–q06 cover assignments, visit order, the NUS-ISS depot, arrival and
completion offsets, unassigned tasks and all four workloads. q06 supplies minutes
without claiming a verified workload ranking. q07 refuses an incomplete GA versus
Greedy comparison. q08 rejects a stale plan before calling the double. q09 covers
matrix provenance; q10 covers missing deadlines. The workflow covers upload,
review, planning, own-crew completion, stale-plan rejection, replanning and
assistant crew adjustment. Its recorded input revisions progress 2 → 3 → 4.

The per-case JSON files retain original inputs, expected outcomes, responses,
plan IDs, revisions, citations and hashes. Unicode escaping changes only their
serialization; Chinese captured text remains the original evidence. Credentials
and sessions were excluded. Synthetic account IDs check ownership. `run.json`
contains the original source hashes and baseline commit; generated IDs, times
and runtime values need not match between executions.
