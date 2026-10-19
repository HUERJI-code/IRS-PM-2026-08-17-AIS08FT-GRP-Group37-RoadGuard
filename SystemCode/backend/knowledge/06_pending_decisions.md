# Pending choices and further evidence

document_id: `rg-kb-pending`; document_version: `5`; owner: `A`.

<a id="pending-business"></a>
## Business and scenario decisions pending

classification: `pending_decision`. citation_id: `rg-kb-pending#pending-business`.

On 2026-10-14, course-simulation demo-rules-v2 durations were finalized: eight severity/priority mappings remain unchanged, with P3/P2/P1 expected service times 60/120/240 minutes. One primary box >= 0.60 automatically creates one task; lower confidence requires review. These durations are neither deadlines nor measured values. Formal engineering rules and real-scenario calibration still lack evidence. A/B must confirm shift length, return-to-depot policy, crew capability assumptions, task deadlines/lateness definitions and objective weights. B must verify vehicle access against the NUS-ISS building reference coordinates; task-road eligibility and real matrix sources also need evidence.

due_at=null means no defined task deadline; return_to_depot=null means no defined return policy. Unknown duration is not zero, no available plan is not a valid empty plan, and unreachable travel is not zero minutes.

Sources: [src-project-config](../../config/project.example.json), [src-demo-rules](../../config/demo_rules.example.json), [context-agents](../../../AGENTS.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md).

<a id="pending-evaluation"></a>
## Algorithm, model and integration evidence

classification: `pending_decision`. citation_id: `rg-kb-pending#pending-evaluation`.

The main comparison uses four crews and 10/15/20 tasks, with identical inputs, travel matrices and constraints for GA and Greedy. B must still deliver encoding, parameters, stopping conditions, objective weights and multiple random seeds; do not claim GA superiority beforehand. Report algorithm runtime, external API waiting and travel/service durations separately. More crews do not imply faster algorithm execution.

Full data-content verification, splits and real-model training/held-out metrics must cite actual records of the corresponding Step 8 run. Valid model numbers do not establish business accuracy acceptance; experimental models are not calibrated automatic-acceptance systems. B's persisted route facts, C's retrieval/citation/confirmation flow and end-to-end integration still require actual deliverables. Package integrity tests and acceptance questions do not prove those capabilities are complete.

Sources: [src-project-config](../../config/project.example.json), [context-agents](../../../AGENTS.md), [context-team](../../../Miscellaneous/TEAM_WORK_ALLOCATION.md), [context-scope](../../../Miscellaneous/PROJECT_SCOPE.md).
