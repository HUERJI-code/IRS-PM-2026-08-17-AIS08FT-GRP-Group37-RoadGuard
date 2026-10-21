# Grounded answers and optional sources

Current contract: **c-assistant-query-v3**; knowledge: **a-knowledge-v19**.

Standalone questions such as "What model are you?" read the configured assistant
model name from the backend. This is configuration information, not a provider's
self-description or proof of model execution. No key is exposed and neither the
provider, knowledge package, Chroma index nor saved-plan store is read. This path
works when generation is disabled or no key is set; missing model names are
reported explicitly. It does not identify the separate YOLO detector.

Clearly unrelated questions receive friendly RoadGuard scope guidance. Bounded
English/Chinese intent matching handles common identity and unrelated topics;
ambiguous or mixed project questions retain the evidence path. Unavailable or
insufficient evidence remains explicit; malformed citations are never hidden by
this guidance. Neither direct path consumes the model call budget or changes
business data. Existing dispatcher authentication, CSRF and request validation
apply to every query.

New response modes are server_configuration (status=model_info) and scope_guidance
(status=out_of_scope). Both have model_called=false, no selections/sources, and
null package_version, manifest_sha256 and plan. RAG retains grounded_summary and
all checks below. Strict clients must update the generated OpenAPI/TypeScript.
The frontend labels the answer origin and permits configuration questions even
when GPT is not configured.
The assistant displays a concise natural-language answer, with original evidence
and version details inside a default-closed sources disclosure (the requested UI
label is “View sources”). Authentication, dispatcher-only access, CSRF and the separate
crew-change confirmation workflow are unchanged.

One Responses API call returns supported, up to six evidence_ids, and an answer
of at most 1,800 characters. The server owns the evidence catalogue and restores
all quotations and required context. Existing hash, substring, duplicate,
damage-row, rule-version and saved-plan revision checks run before composition.
Knowledge answers using canonical repair rows are rendered directly from those
rows in English, including for Chinese questions, preserving project-assumption qualifiers and
avoiding generated numerical rule values. Saved-plan answers keep saved facts.
Other questions use the model draft, rejecting numbers, P1/P2/P3 priorities and
crew/task/plan identifiers absent from the selected evidence. The checks do not
prove semantic entailment or detect every possible mistaken relationship.

answer is prose; selections and sources are still the exact, auditable evidence.
Clients must accept the three answer_mode values and c-assistant-query-v3 instead
of assuming answer is a concatenation of quotes. OpenAPI, generated TypeScript
and the frontend test fixture are updated together. Answers render as plain text.
The source disclosure resets after a new question. No additional model call,
business write, credential change, automatic retry or database migration is added.
Rebuild the local Chroma index using the command below after a source update.

Current intent-routing acceptance is recorded in the
[query-v3 acceptance record](../../../../Miscellaneous/RAG_INTENT_ROUTING_ACCEPTANCE_20261021.md).
The earlier [answer-first acceptance record](../../../../Miscellaneous/RAG_ANSWER_FIRST_ACCEPTANCE_20261021.md)
documents the preceding display and grounding changes.
The following sections document the prior evidence-only release and original
integration; the current query-v3 contract above supersedes v1 answer rendering.

## Current task adjustments and persistence

Business schema v6 and `c-assistant-task-change-v1` support dispatcher-only route previews, task reassignment and cancellation. Load an explicit saved plan or latest GA plan, review four-crew travel/service/return totals, preview a move or cancellation, acknowledge and confirm. Preview preserves all other assigned work and rejects unknown travel, overtime, stale input/configuration and expired records. Confirmation atomically persists the crew constraint or workflow cancellation with receipts and history; recalculation is a separate explicit action.

Greedy and GA honor durable constraints after restarts and new tasks. Infeasible or unavailable constrained tasks are explicitly unassigned; stop order may change. Cancelled records remain in history and leave active planning. Discarding a preview does not cancel a task. Recent records and change IDs support idempotent recovery. Reassignment immediately revokes the old crew's task/inspection access; the new crew waits for a saved GA recalculation. Backend checks preserve dispatcher, crew and inspector boundaries.

See the [complete user guide](../../../../ProjectReport/INSTALLATION_AND_USER_GUIDE.md) for setup and operations, and the [task-adjustment acceptance](../../../../Miscellaneous/TASK_ADJUSTMENT_ACCEPTANCE_20261021.md) for bounded HTTP, browser and provider evidence. Earlier schema-v5 and query-v1/v2 sections below describe historical releases, not the current contract.

## Previous evidence-only behavior (2026-10-21)

The preceding evidence-only release used **a-knowledge-v13**. The public `c-assistant-query-v1`
request/response fields and dispatcher permissions are unchanged. No frontend,
database schema, repair rule, credential or model configuration change is needed.

GPT previously copied quote text and could join nonadjacent paragraphs/table
rows or choose `alligator_crack_sunken` for a `pothole_deep` question. Equal P1 /
240-minute values do not make these labels interchangeable.

That release receives a catalogue of exact paragraphs and table rows, and
returned only `supported` and up to six `evidence_ids` using a strict enum schema.
The backend restores quotations from those IDs. Selected rule rows carry their
original column header, rule version and demo limitations as a **separate**
verbatim selection; the combined display is never validated as one fabricated
quote. Context is deduplicated, with at most twelve resolved selections.

For explicit English/Chinese class aliases, longest non-overlapping matches keep
deep/sunken/wide classes distinct. Only matching rows of the two canonical tables
are selectable; comparison answers must cover all named labels. This bounded
terminology guard is not a general language parser: unknown paraphrases, negation
and broad semantic sufficiency still need evaluation. General table questions
can select the complete original table. No rule numbers are duplicated in code.

Source hashes and provenance, exact substring membership, catalogue membership,
required context, duplicate rejection, requested rule versions, saved-plan
revision checks, role checks and CSRF remain enforced. There is no automatic
retry, permissive quote repair, generated-text fallback or business write.
An invalid ID/quote remains `502 assistant_invalid_response`; incomplete table
comparisons return `200 insufficient_data` with no partial answer.

After pulling this change, rebuild the local index using the existing cached E5
model and restart the backend (or let Uvicorn reload):

```powershell
$env:PYTHONPATH = 'SystemCode/backend'
.\.venv\Scripts\python.exe -m roadguard.assistant.index_knowledge
```

Run `python -m pytest SystemCode/tests/test_assistant_evidence.py
SystemCode/tests/test_assistant_query.py SystemCode/tests/test_knowledge_handoff.py
SystemCode/tests/test_knowledge_retrieval.py SystemCode/tests/test_vector_retrieval.py -q`
as one command. Automated tests use provider/embedding doubles and temporary
databases. Real configured-model acceptance is recorded separately in
[the rule citation acceptance record](../../../../Miscellaneous/RAG_RULE_CITATION_ACCEPTANCE_20261021.md).
The original Chroma [setup guide](VECTOR_RETRIEVAL.md) still applies.

The ID-only response follows the official
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).
Schema validity alone does not establish semantic relevance.

---

# ChromaDB and local embeddings (2026-10-21)

Current setup and maintenance: [Vector retrieval](VECTOR_RETRIEVAL.md). This historical release used a-knowledge-v12. ChromaDB stores static passages with local E5 embeddings; original role, source-validation and confirmed-change contracts remain. The delivery records below describe earlier lexical versions.

# Historical merged assistant package (2026-10-21)

The historical v11 integration introduced: all eleven English knowledge documents from main, 40 sections, 30 synthetic acceptance specifications and the two stable feature citations for routing defaults and account roles. The loader accepts English and original full-width metadata punctuation. Retrieval preserves English terms and a bounded set of Chinese domain aliases; this is not a general translation service. Sources are revalidated on each request.

The records below describe C's earlier six-document/v9 implementation and pre-merge acceptance. They remain historical and do not override the current manifest. GPT remains opt-in and was not called during merge verification. Broad questions may exceed the existing 24,000-character provider context budget and return an explicit size error; no paid budget or silent truncation was added.

## Historical C delivery notes

## Historical Steps 10–12 (English display summary)

This section summarizes prior deliveries; it is not a new execution record.
The original text is preserved losslessly in
[historical-readme-originals.json](../../../experiments/assistant/historical-readme-originals.json).

Step 10 provided read-only lexical search through
`POST /api/v1/assistant/knowledge/search` (`c-knowledge-search-v1`). It required
a dispatcher session, CSRF token and same-origin request. Queries contain 2–500
characters, limits are 1–8 (default 5), and optional rule versions must match.
Results distinguish matches, no matches and unavailable rule versions. Every
request validates the manifest, pinned source hashes, stable citations and path
boundaries. The historical v9 package had six documents and nineteen sections.
Search results are candidates, not generated answers or confidence scores.

Step 11 added dispatcher-only query and status endpoints. Knowledge questions
accept no plan ID; plan questions require a saved `plan-` plus 32 hexadecimal
characters. Evidence comes from authorized saved plans, not browser-supplied
facts. The historical v1 answer used verified verbatim extracts. Unsupported,
stale, unavailable-version and refused requests return no partial model answer.
Source or plan changes during a request discard the output. The current query-v3
summary behavior described above supersedes that rendering.

The provider is disabled by default. Server configuration uses
`ROADGUARD_ASSISTANT_ENABLED`, `OPENAI_API_KEY`, `ROADGUARD_ASSISTANT_MODEL`,
`ROADGUARD_ASSISTANT_MAX_OUTPUT_TOKENS` (1200, range 256–2000), and
`ROADGUARD_ASSISTANT_MAX_CALLS` (20 per process, range 1–200). Failed attempts
count. Limits include 24,000 input characters, 128,000 response bytes, six
selected evidence units, 2,400 characters per unit, two concurrent calls and
six attempts per account per minute. Counters reset with the process and are
not a deployment-wide billing cap. There are no automatic retries or model
fallbacks. Socket timeout is twenty seconds; cancelling the sixty-second UI
wait does not guarantee cancellation of upstream usage.

Requests use the fixed Responses endpoint, no redirects, `store=false`, no tools
and no conversation history. Only the question and bounded knowledge/plan
projection are sent; account details, images, task coordinates and raw database
records are excluded. `store=false` does not establish zero provider retention.
The status endpoint reports configuration and usage, not credential validity.
Historical automated acceptance used explicit provider doubles; these records
do not establish real GPT answer quality.

Step 12 added persistent crew-change previews, confirmation, cancellation,
history and explicit replanning, under `c-assistant-change-v1`. Records are scoped
to the authenticated dispatcher. Preview expiry is fifteen minutes. Confirmation
checks input and crew versions and atomically saves the crew state, receipt and
audit event through the crew service. Repeated confirmation returns its receipt;
a no-op does not increment the input revision. Historical receipts are not live
crew status. Replanning is a separate explicit action: failure retains confirmed
crew changes, with no automatic retry or rollback. Attempts are idempotent,
limited to ten, with a ten-minute execution lease. A new attempt can recover
after interruption; an old attempt cannot overwrite a newer result. Plan saving
and the success receipt share a transaction. Later input changes require a new
preview. Restoring state also requires a fresh opposite preview.

Schema v5 added `assistant_changes` and `assistant_change_events` while preserving
business data. Migration and workflow tests used isolated databases. Existing
developer databases were not migrated for those tests. Back up operational
data before starting a newer backend. The frontend treats interrupted writes
as uncertain and supports record lookup instead of automatic resubmission.
Tests cover permissions, CSRF, ownership, parsing, expiry, concurrency, rollback,
replay, failures and recovery. Real model and external travel calls were absent.

## Task adjustments (2026-10-21)

The Crew adjustments tab includes task routes for an explicit saved plan or the
latest GA plan. Load the plan, select an assigned task and target crew (or cancel
an active task), then preview. The server compares before/after routes and total
travel plus service plus configured depot return. Confirmation is explicit;
recalculation is a separate action. A confirmed crew assignment is persistent
across later planning runs. If the selected crew becomes unavailable or the task
cannot fit, the planner reports it unassigned instead of moving it silently.

`/api/v1/assistant/task-changes` exposes preview, list, get, confirm, cancel-preview
and replan under `c-assistant-task-change-v1`. It requires dispatcher authorization
and CSRF on writes. It does not use GPT. Schema v6 adds receipts, audit events and
task-to-crew constraints; cancellation calls the existing workflow service so task
history is preserved. Stale revisions/configuration, expired previews and repeated
requests have explicit outcomes. Neither free-form chat nor source material can
confirm a change. See the [API contract](../../../../Miscellaneous/API_CONTRACT.md).
