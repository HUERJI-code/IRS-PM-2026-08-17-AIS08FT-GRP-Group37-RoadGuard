# RAG branch synchronization and verification

Date: 2026-10-21. Coordinator: A. Feature owner: C.

## Scope

Merge `origin/main` at `4c5bb12034d099ad92188f457a6e1133c6ceca1d` into
`feature/c-knowledge-retrieval` at `63a54fa42a3de8ffc4dcc64ccc430ff924d9ea64`.
The branches diverged before the English conversion and the expanded knowledge
handoff. Sixteen paths required conflict resolution. This synchronization keeps
both histories and does not authorize a direct push to main.

## Resolution

- Preserve main's English navigation, existing account permissions, report files
  and expanded GA, routing, operations and evaluation knowledge.
- Retain C's retrieval, optional GPT evidence selection, dispatcher assistant and
  persistent crew-change preview, confirmation, cancellation and explicit
  replanning workflow, including database schema version 5.
- Publish `a-knowledge-v11` with eleven English documents, 40 sections and 30
  synthetic acceptance specifications. Preserve the feature's stable routing
  defaults and account-role citations, and refresh document/source hashes.
- Accept both English and original full-width metadata punctuation. Exclude
  source metadata from retrieval terms and answer excerpts. Preserve the existing
  Chinese domain queries through bounded lexical aliases, with English retrieval
  regression cases. This does not provide general multilingual translation.
- Reconcile the shared API documentation and distinguish the feature's historical
  v9 acceptance records from the current package. The existing single-box output,
  0.60 automatic-task threshold and repair durations remain unchanged.

## Verification

All checks ran locally with temporary databases and controlled provider doubles;
no live application database, training process or paid provider was used.

| Check | Result |
| --- | --- |
| Complete backend suite after the main conflict resolution | 1127 passed, 2 skipped |
| Final knowledge handoff, retrieval and assistant query regression after metadata cleanup and source refresh | 140 passed, 1 skipped, including five added metadata cases |
| Frontend test suite | 166 passed across 14 files |
| Frontend ESLint, TypeScript and Vite production build | Passed |
| Backend OpenAPI against the checked-in frontend snapshot | Matched |
| Repository structure and local Markdown links | Passed |
| Whitespace and unresolved conflict-marker checks | Passed |

The backend emitted an existing Starlette/httpx deprecation warning. Vite emitted
its large-bundle warning. Neither prevented the checks from completing.

## Limits and preserved local work

Real GPT connectivity and semantic answer quality were not tested. The existing
24,000-character context limit remains; broad questions can return an explicit
size error. The original feature's acceptance fixtures are historical evidence,
not new real-provider results. No new browser or production acceptance is claimed.

The fourteen pre-existing uncommitted YOLO files were isolated before switching
branches and are excluded from this merge. Dataset files, training checkpoints,
credentials and runtime database files are not added. Restore those local files
after delivery and verify their saved SHA-256 values.

The delivery target is the existing feature branch. A pull request and its GitHub
checks are separate from these local verification results.
