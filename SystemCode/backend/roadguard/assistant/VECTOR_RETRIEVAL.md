# Local vector retrieval

The dispatcher assistant uses ChromaDB 1.5.9 with local multilingual E5 embeddings.
The embedding encoder uses ONNX Runtime on CPU; it does not alter the YOLO/PyTorch
model, call an embedding API, or train a model. GPT evidence selection and English grounded summaries remain a
separate opt-in service. The current reviewed package is a-knowledge-v18 and the
query contract is c-assistant-query-v3. The existing role, CSRF, citation and confirmation checks
remain in place.

## Setup

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r SystemCode/backend/requirements.txt
$env:PYTHONPATH = 'SystemCode/backend'
.\.venv\Scripts\python.exe -m roadguard.assistant.index_knowledge --download-model
```

The first setup downloads approximately 487 MB from the public
[multilingual-e5-small repository](https://huggingface.co/intfloat/multilingual-e5-small).
Both files are pinned to revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` and
verified against their official LFS SHA-256 hashes. Subsequent setup verifies and
reuses the model. HTTP requests never download models or rebuild indexes.

Default local paths, relative to the repository regardless of the current directory:

| Resource | Path |
| --- | --- |
| Chroma database and vector segments | `SystemCode/backend/data/rag/chroma/` |
| Embedding model and tokenizer | `SystemCode/backend/data/rag/models/multilingual-e5-small/` |
| Authoritative source documents | `SystemCode/backend/knowledge/` |

The complete `SystemCode/backend/data/` tree is ignored by Git, including Chroma's
binary segments and tokenizer files. Dataset, uploads, business databases and
account records are not indexed. Use `ROADGUARD_CHROMA_PATH` and
`ROADGUARD_EMBEDDING_PATH` only for server-side path overrides. A local
[Chroma PersistentClient](https://docs.trychroma.com/reference/python) fits this
single-machine deployment; a shared production service needs a separate deployment
decision. Chroma's own local SQLite files do not replace RoadGuard's business DB.

## Index and retrieval

1. Verify the knowledge manifest, source files and stable section citations.
2. Remove source bookkeeping and split section text into at most 320-token
   passages with 48-token overlap. Retain exact character spans and parent IDs.
3. Prefix documents with `passage: ` and questions with `query: `. Compute masked
   mean pooling and L2-normalized 384-dimensional embeddings, following the
   [model's documented inference procedure](https://huggingface.co/intfloat/multilingual-e5-small#usage).
   The 512-token model limit is checked; oversized inputs fail explicitly.
4. Store vectors, text, citation IDs, document/package versions, classification,
   source IDs and hashes in Chroma. The collection identity includes the manifest,
   encoder revision and chunking policy. A write lock serializes index builds.
5. Use [cosine distance](https://docs.trychroma.com/docs/collections/configure),
   rank each parent by its best matching passage and return the complete verified
   parent section, preserving table rows and nearby limitations. Only matched sections enter GPT context; unrelated sibling
   sections are no longer appended.

`score` is cosine similarity, not confidence or answer correctness. The default
candidate cutoff is `0.78`, configurable with `ROADGUARD_RAG_MIN_SIMILARITY` in
the range 0–1. This is a retrieval heuristic requiring evaluation, not a calibrated
probability. GPT still decides whether the provided evidence supports an answer,
and the server verifies exact quotations. There is no silent lexical fallback.

## Maintenance and failures

After reviewing a knowledge/source update, refresh the package version and hashes,
then run `python -m roadguard.assistant.index_knowledge` with the backend on
`PYTHONPATH`. Repeating the command verifies and reuses a completed current index;
it does not add duplicate rows. New versions use separate collections. An
interrupted build is not marked ready and can be rerun. Old versions are retained
but never substituted for the current manifest.

The query API returns an explicit 503 for a missing model, absent/stale index or
invalid stored provenance. Other backend modules remain available. Check returned
`code`: `embedding_model_unavailable`, `knowledge_index_unavailable`, or
`retrieval_configuration_error`. Inputs beyond the encoder limit return
`retrieval_input_too_long` (422). The GPT context limit remains a separate check.

`POST /api/v1/assistant/knowledge/search` now returns `c-knowledge-search-v2` and
`retrieval_method=chroma-e5-cosine-v1`. Existing result fields and stable parent
citations remain; `matched_terms` is an empty compatibility field. Search does not change business data. Answering uses query-v3; availability changes
use change-v1 and task adjustments use task-change-v1. Only dispatcher sessions may use these APIs.

## Verification boundaries

Automated control-flow tests use real temporary Chroma databases and explicit
embedding doubles, so CI requires neither a model download nor paid API access.
They cover persistence, duplicate builds, incomplete builds, source/version
changes, tampering, missing models, permissions and read-only answering.
Real E5 retrieval must be evaluated separately against saved expected citations;
do not report the doubles as semantic accuracy or a successful real GPT call.

Targeted real E5 and configured GPT cases are recorded in the [intent-routing acceptance](../../../../Miscellaneous/RAG_INTENT_ROUTING_ACCEPTANCE_20261021.md), whose historical package was v16. They demonstrate bounded source agreement and provider connectivity, not broad semantic accuracy. Refreshing the current v18 package requires the explicit index command above; do not reuse a stale collection as a fallback.
