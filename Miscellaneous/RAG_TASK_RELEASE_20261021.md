# Assistant and task adjustment release

Release date: 21 October 2026. Code [PR 36](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard/pull/36) was automatically merged as `b8d0fdea1480e3f5d79706a8e5d443da4ad74f33` after all required checks passed. The subsequent [main CI](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard/actions/runs/39569838277) also passed. This record distinguishes publication verification from the earlier, bounded functionality experiments.

## Delivered behavior

- Repair and saved-route answers retain source IDs, exact quotations, rule/label checks and saved-plan freshness validation. Canonical repair answers use matching verified rows; other summaries have bounded factual guards. English prose appears first, with View sources closed by default.
- Query-v3 answers standalone model-identity questions from non-secret backend configuration and gives scope guidance for clearly unrelated questions without provider/retrieval calls. Mixed or project questions keep the evidence flow.
- Dispatcher task previews show all four saved crew routes. Confirmed moves check travel, service and required return against the shift without dropping other assigned tasks. Persistent crew constraints survive restart and later GA/Greedy recalculation; unavailable or infeasible constrained work remains explicitly unassigned.
- Cancellation retains task history and removes active work. Preview, confirmation and recalculation remain separate, with version, expiry, role, CSRF and idempotency checks. Previous-crew access ends on confirmed reassignment; target-crew access follows an updated saved GA plan.

## Release checks

| Check | Recorded outcome | Interpretation |
| --- | --- | --- |
| Independent functional review | No blocking finding | Reviewed task persistence, feasibility, authorization and answer boundaries |
| Linux Python 3.11, PR head `155d318345cf48802a1e4a9b3135d60b212bcb91` | 1,255 passed; one optional YOLO test skipped | [GitHub run 39569241424](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard/actions/runs/39569241424); base dependencies do not establish full vision-runtime installation |
| Clean-checkout frontend | 179 passed; lint, TypeScript and production build passed | Existing bundle-size warning remains |
| Infrastructure guardrails | 49 passed | Repository/PR/automatic-merge policy checks |
| Exact published paths | 105 verified paths | No extra files in the GitHub PR |
| Excluded training work | All 14 original files remained byte-identical | No training changes were staged or published |

The first full run found two obsolete exact-inventory assertions: the expected API paths and database tables did not include the new task-adjustment entries. Updating those assertions passed the two focused checks and the complete GitHub suite. No validation was disabled. Earlier targeted suite counts overlap with this full run and are not additive.

## Evidence and limitations

Historical records retain their executed package versions and values:

- [Rule citation repair](RAG_RULE_CITATION_ACCEPTANCE_20261021.md)
- [Answer-first presentation](RAG_ANSWER_FIRST_ACCEPTANCE_20261021.md)
- [Task adjustments](TASK_ADJUSTMENT_ACCEPTANCE_20261021.md)
- [Intent routing](RAG_INTENT_ROUTING_ACCEPTANCE_20261021.md)

Actual GPT calls, local E5 retrieval, provider doubles and constructed routing cases are distinct evidence. In particular, the intent record contains four local direct cases without model calls and two actual GPT cases using the then-current package. Successful source agreement in these cases is not a broad semantic accuracy score, completion of every proposed evaluation case, or operational engineering approval.

The post-push documentation refresh uses `a-knowledge-v17`, revises current scope/status wording and pins the reviewed guide/source bytes. It preserves original citations, label/rule values and historical experiment records. Pulling this package requires the explicit [local index rebuild](../SystemCode/backend/roadguard/assistant/VECTOR_RETRIEVAL.md), using cached embeddings where available. Runtime databases, vectors, model caches, credentials and Dataset remain outside Git.

The v17 documentation change passed 107 focused knowledge/retrieval checks, with one Windows symlink test skipped. A cached real-E5 rebuild produced 66 indexed passages. [Authenticated read-only HTTP verification](../SystemCode/experiments/assistant/documentation-v17-verification-20261021.json) retrieved the correct rule-table citation, verified direct model/scope response modes, consumed zero GPT calls and left the business input revision unchanged. This verifies the refreshed package's local operation without claiming a new GPT answer-quality experiment.

The [current report](../ProjectReport/README.md) incorporates the delivered workflows, bounded acceptance, complete user guide and course mapping. Independent clean-machine installation, broad assistant reliability evaluation, field calibration and final video/package completion remain separate outstanding work.

The final report has 42 visually verified pages and 32 current linked contents entries. The complete seven-page user guide, original thirteen-page proposal and one-page course mapping remain in Appendices A/B/C. All original embedded images and numerical vision/routing tables are preserved; Assignment and repository DOCX copies are identical.
