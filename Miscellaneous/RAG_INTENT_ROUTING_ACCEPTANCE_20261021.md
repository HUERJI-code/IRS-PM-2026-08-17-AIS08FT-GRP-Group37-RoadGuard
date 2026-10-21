# Assistant intent routing acceptance

Date: 2026-10-21. Owner: C, with primary-agent integration and review.
Delivery: local only; no commit, push or pull request. Existing training changes
and all prior task-adjustment/answer-first work were preserved.

## Behavior and contract

The query-v3 response distinguishes server_configuration, scope_guidance and
grounded_summary. Standalone model identity questions read the configured model
name without GPT, retrieval or saved-plan reads. Missing configuration is explicit;
no API key is returned. Clearly unrelated questions receive RoadGuard examples.
Direct responses have empty citations and null knowledge/plan metadata. They still
require dispatcher authorization, CSRF and valid request fields.

The identity matcher covers whole English/Chinese questions. Explicit unrelated
topics are bounded; domain terms take precedence. Ambiguous or mixed questions
retain the evidence flow. This is not unrestricted intent understanding. Existing
forged-citation, exact-quote, damage-row, rule-version, numeric/priority/identifier
and saved-plan freshness checks remain. Model output that fails validation is
still rejected; it is not relabelled as a friendly answer.

Frontend responses identify their origin, retain the answer-first layout and
default-closed sources, and allow model-configuration questions when GPT is not
configured. OpenAPI, TypeScript types, the synthetic fixture and module guides
were updated together. The reviewed knowledge package is a-knowledge-v16; the
local Chroma index was rebuilt with cached E5 weights (63 passages, 384 dimensions).
No business schema, account permission or model deployment change was required.

## Automated verification

Commands ran from the repository root unless noted. No provider calls occur in
these suites; they use temporary databases and controlled provider doubles.

| Check | Result |
| --- | --- |
| `pytest SystemCode/tests/test_assistant_intents.py -q` | 24 passed |
| `pytest SystemCode/tests/test_assistant_query.py SystemCode/tests/test_c_acceptance.py -q` | 78 passed |
| `pytest SystemCode/tests/test_knowledge_handoff.py SystemCode/tests/test_knowledge_retrieval.py SystemCode/tests/test_assistant_evidence.py SystemCode/tests/test_assistant_answering.py -q` | 151 passed, 1 Windows symlink test skipped |
| Frontend `vitest run src/pages/AssistantPage.test.tsx src/api/api.test.ts` | 30 passed |
| TypeScript no-emit and focused frontend ESLint | Passed |
| Vite production build | Passed; existing large-bundle warning remains |
| Repository check and OpenAPI snapshot comparison | Passed |

HTTP tests needed local sockets outside the sandbox. Initial sandbox runs that
stalled at TestClient startup were stopped and rerun; they are not counted as
passes. Final source normalization changed line endings only. The knowledge
loader and live retrieval endpoint were checked against the final hashes.

## Live and browser verification

The running backend reported configured model `gpt-4.1-mini`. Four direct API
questions covered English/Chinese model identity, Singapore weather and the World
Cup. All returned HTTP 200 with no citations, no provider call and no quota change.
Browser checks independently displayed the configuration answer and scope guidance
without validation errors; the user's existing tab and answer were preserved.

Two real configured-model questions then passed:

1. Deep-pothole repair priority and service duration: P1, 240 minutes, high severity.
   The selections included the exact pothole_deep row and excluded the sunken
   alligator row. The answer retained the project-assumption qualification.
2. Saved-plan travel/service totals: 98.8 and 165.0 minutes, matching the selected
   persisted plan. Sources included its summary and metrics. Historical task
   durations were not recalculated using the newest rules.

Every selected quotation was an exact substring of its returned source. Tasks,
crews and the selected saved plan were unchanged before/after these calls. These
two cases demonstrate targeted real connectivity and factual agreement, not broad
semantic correctness. Raw, sanitized responses and the final index check are in
[the execution record](../SystemCode/experiments/assistant/intent-routing-20261021.json).

All fourteen pre-existing model-training files matched their earlier byte hashes.
Dataset, runtime databases, vector indexes and model caches remain local; no Git
publication occurred.
