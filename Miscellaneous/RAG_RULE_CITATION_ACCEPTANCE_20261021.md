# RAG rule citation repair and local acceptance

Date: 2026-10-21. Owner: A coordinates business evidence with C's assistant module.
Delivery: local branch `fix/c-rag-rule-evidence`; no commit, push or PR in this task.
Baseline main was synchronized with origin at `7537658f852ae712420ffe418b1aeff15eef31c6`.

## Defect and implementation

The live deep-pothole question previously returned `502 assistant_invalid_response`.
A diagnostic call produced a quote assembled from nonadjacent source passages and
selected `alligator_crack_sunken` instead of `pothole_deep`. Both happen to have P1
and 240 minutes, but they are different labels. The original substring check
correctly blocked the fabricated quotation; it did not by itself enforce label relevance.

[Evidence units](../SystemCode/backend/roadguard/assistant/evidence.py) now divide
verified parent sections into exact source spans. GPT returns only evidence IDs
from a bounded enum. The backend restores text and required table context itself.
English/Chinese aliases use longest non-overlapping matches so qualified labels
do not become base labels. Specific label questions expose only matching rows of
the rule/label tables. General table questions retain the whole original table.
The table introduction, version, demo qualification and column header remain a
separate exact quotation; separated rows are never described as contiguous text.
Long multiline route projections retain all lines in bounded contiguous units.

The original citation, source hash, exact-substring, duplicate, rule-version,
saved-plan revision, dispatcher permission and CSRF checks remain. Catalogue
membership, required context and named-label coverage add further checks. Partial
table comparisons return insufficient_data with no partial answer. There are no
automatic paid retries, fuzzy quote repair, invented rule values or business writes.

Public `c-assistant-query-v1` fields are unchanged. The internal model schema is
now `supported` plus up to six `evidence_ids`; the response can contain up to twelve
verbatim selections after required context expansion. No frontend or DB migration
is needed. Knowledge package `a-knowledge-v13` updates provenance, retaining the
same eight labels and demo-rules-v2 values. The local Chroma index was rebuilt
with the existing cached E5 model: 58 passages, 40 parent sections, 384 dimensions.

## Automated verification

Commands run from the repository root using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest SystemCode/tests/test_assistant_evidence.py SystemCode/tests/test_assistant_query.py SystemCode/tests/test_knowledge_handoff.py SystemCode/tests/test_knowledge_retrieval.py SystemCode/tests/test_vector_retrieval.py SystemCode/tests/test_c_acceptance.py SystemCode/tests/test_assistant_changes.py -q
```

Result: **235 passed, 1 skipped**. The skipped case requires OS permission to
create a test symlink. These tests use controlled provider/embedding doubles and
temporary databases; they do not demonstrate real GPT semantic accuracy.

The final refinement added four cases for long route evidence and English token
boundaries. `test_assistant_evidence.py`: **29 passed**. The affected HTTP, C-role
acceptance, knowledge integrity and vector modules were then rerun together:
`test_assistant_query.py`, `test_c_acceptance.py`, `test_knowledge_handoff.py`,
`test_vector_retrieval.py`: **150 passed**. These overlapping runs are not summed
as independent samples. Isolated test directories were used; the first restricted
environment run stalled and was stopped, then the tests completed outside that
environment. Initial metadata synchronization errors were corrected before the
passing runs; source validation was not weakened.

Covered regressions include all eight label mappings in English and Chinese,
ordinary/deep and ordinary/sunken distinctions, wide/base crack comparisons,
real-but-wrong table rows, fabricated concatenations, missing context, unknown or
duplicate IDs, extra generated quote fields, incomplete comparisons, unknown rule
versions, stale plans, role/CSRF failures and unchanged business data.

## Real configured-model checks

Model: `gpt-4.1-mini`, enabled through the user's existing local PyCharm configuration.
This task made eight model requests: seven authenticated API checks through the
frontend proxy and one browser check. No automatic retry was used. Credentials,
cookies, API keys, raw vectors and model caches are excluded from this record.
The [sanitized result summary](../SystemCode/experiments/assistant/rule-citation-live-20261021.json)
distinguishes API evidence checks from browser observations.

| Case | Observed result | Evidence check |
| --- | --- | --- |
| Ordinary pothole, Chinese | pothole / medium / P2 / 120 minutes | Matching rule row; original quote and source metadata verified |
| Sunken alligator crack, Chinese | alligator_crack_sunken / high / P1 / 240 minutes | Correct qualified class; no substitution by pothole_deep |
| Ordinary alligator crack, Chinese | alligator_crack / medium / P2 / 120 minutes | Correct unqualified class |
| Ordinary versus wide longitudinal crack, Chinese | P3 / 60 versus P2 / 120 minutes | Both named rows returned separately with shared original context |
| Deep pothole, English | pothole_deep / high / P1 / 240 minutes | Matching row and exact source quotations |
| Saved plan travel and assigned count | 98.8 minutes and 2 tasks | Exact agreement with the selected saved simulated plan |
| Unrelated stock recommendation | insufficient_data; no sources or selections | No unsupported answer |
| Original deep-pothole question, browser | pothole_deep / high / P1 / 240 minutes | Successful displayed answer, separate context/row and original source link |

All seven API checks returned HTTP 200 and met their expected assertions. Every
returned static source matched the verified package content, document hash,
version and provenance; every quote was an exact source substring. Dynamic plan
evidence matched the saved-plan projection. Business-table hashes remained
unchanged around the API tests. The browser displayed a-knowledge-v13, the actual
model name and business_changes_applied=false. No tasks, crews or plans were changed.

## Limits and handoff

This is targeted defect acceptance, not an overall RAG accuracy benchmark.
Aliases cover known terminology, not arbitrary paraphrases or negation. The model
can still select incomplete evidence; complex questions may decline. Source
integrity does not establish engineering suitability, and the rule durations
remain simulation assumptions. Broader semantic evaluation remains pending.

After pulling an eventual publication, follow the [assistant guide](../SystemCode/backend/roadguard/assistant/README.md)
to rebuild the versioned local Chroma index and restart/reload the backend. Existing
API key/model settings and public frontend contracts remain compatible. The local
frontend and backend were left running for review. Dataset, vector databases,
model caches and the pre-existing YOLO training changes are outside this delivery.
