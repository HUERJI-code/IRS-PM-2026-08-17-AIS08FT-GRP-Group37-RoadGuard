# Answer-first RAG acceptance — 21 October 2026

Owner: A, coordinating C's assistant and frontend. Delivery: local working tree
only; no commit, push or pull request was requested for this change.

## Result and caller impact

The assistant now displays a readable answer first. Original quotations, source
versions, hashes, provenance and detailed limitations remain accessible inside a
default-closed sources disclosure, originally labeled with the Chinese equivalent of “View sources”; the current UI uses English.
The answer is rendered as plain text. Entering a new question clears the prior
answer and restores the closed disclosure state.

The public response is **c-assistant-query-v2**, with
**answer_mode=grounded_summary**. The request, route and permissions are unchanged.
OpenAPI, generated TypeScript, the synthetic frontend fixture and module guides
were updated together. One configured GPT call selects evidence IDs and drafts
the answer. The backend restores the original evidence rather than accepting
model-authored quotations. Canonical repair-table answers are rendered from
validated rows, preserving type, severity, priority and duration. Other answers
use the model draft with bounded checks against selected evidence for numerical
literals, priorities and crew/task/plan identifiers.

Exact citation membership, source hashes, contiguous quote matching, duplicate
rejection, required context, named damage-row coverage, requested rule version,
saved-plan freshness, dispatcher permissions and CSRF remain enforced. Unsupported
provider prose is discarded; an unsupported response without evidence displays
the service's own insufficient-data message. Unsupported responses carrying
evidence IDs, malformed output and unverifiable supported answers still fail
validation. No question performs a business change or an automatic retry.

## Automated checks

- Seven affected backend modules initially passed **231 tests**, with **one
  Windows symlink-permission skip**: answer composition, evidence selection,
  authenticated queries, C acceptance, knowledge handoff, retrieval and vectors.
- After refining refusal handling, query and knowledge-handoff tests passed
  **122 tests**. After adding Chinese identifier-boundary coverage, answering,
  evidence and knowledge-handoff tests passed **110 tests**. These runs overlap;
  their totals must not be added together.
- The frontend suite passed **167 tests across 14 files**, including default
  folding, disclosure toggling, reset after a new answer, plain-text escaping,
  cancellation, errors and existing role/crew workflows.
- Frontend ESLint, TypeScript and production build passed. Vite reports the
  existing bundle-size advisory; the build succeeds.
- Backend OpenAPI matches the frontend snapshot. The final knowledge package is
  **a-knowledge-v14**; the cached multilingual E5 model rebuilt a local index with
  **58 vectors, 40 parent citations and 384 dimensions**. No weights were downloaded.

Provider/embedding doubles were used in automated tests. Real model results below
are separate evidence, not implied by automated test success.

## Real configured-model acceptance

Seven bounded calls were made with the configured **gpt-4.1-mini**: six distinct
cases, plus one corrective retest. Five cases used the authenticated local API;
the Chinese deep-pothole case was submitted in the real browser.

| Case | Observed result |
| --- | --- |
| Ordinary versus wide longitudinal crack | Separate natural-language paragraphs: P3 / 60 minutes and P2 / 120 minutes, with the project-assumption qualification. |
| Deep pothole, English | P1 / 240 minutes / high severity; readable English rather than a Markdown table row. |
| Project depot and crew count | NUS-ISS, 25 Heng Mui Keng Terrace, four crews; retained the simulated-origin qualification. |
| Explicit saved plan | 98.8 travel minutes and two assigned tasks, matching B's persisted facts. These are historical saved facts, not a new planning calculation. |
| Unrelated stock-purchase request | Initial request returned 502; after refusal normalization, the single corrective retest returned 200 insufficient_data with no sources. No investment answer was displayed. |
| Deep pothole, Chinese, browser | Clear P1 / 240-minute / high-severity answer. Sources initially closed; expanding them exposed the exact pothole_deep row and separate original context, version and hash. |

For the successful API cases, every returned original quotation was checked
against its source. Static source text, document version, digest and provenance
matched the loaded package; dynamic sources matched B's saved-plan projection.
Non-authentication business-table hashes were unchanged before/after testing.
The initial unrelated failure was retained in the experimental record; the
unsupported response body did not expose provider text or credentials.

The browser was also checked at a 390 × 844 viewport. The content area was 375
pixels wide after the browser scrollbar; scroll width also measured 375 pixels
with sources both closed and open. The normal viewport was restored afterwards.
Desktop and mobile screenshots were saved locally. No browser-only fixture was
substituted for the real answer.

Machine-readable results: [answer-first live record](../SystemCode/experiments/assistant/answer-first-live-20261021.json).
The earlier [rule-citation record](RAG_RULE_CITATION_ACCEPTANCE_20261021.md) remains
historical evidence for the preceding evidence-only behavior.

## Limits and repository hygiene

The guards do not prove that every sentence follows semantically from the source.
Numbers appearing somewhere in selected evidence do not prove a correct
relationship, and bounded label aliases do not understand all paraphrases or
negation. Rule summaries deliberately use controlled wording; compound questions
may need narrower follow-up questions. This is targeted acceptance, not a general
RAG accuracy benchmark or engineering approval.

The fourteen pre-existing model-training files were preserved against their saved
SHA-256 baseline. Dataset, runtime databases, vector storage and model caches remain
ignored. No task, crew, plan or business-rule value was changed by this work.
