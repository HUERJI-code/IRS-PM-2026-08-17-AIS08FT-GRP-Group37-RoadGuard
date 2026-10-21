# Assistant experiment evidence

These are historical captured experiments, not executions of the current English
UI. Original Chinese strings in JSON are preserved using lossless Unicode escapes.
[Serialization provenance](english-display-provenance.json) lists original and
current file hashes. Existing source hashes and result values were not refreshed.
[Original historical README text](historical-readme-originals.json) preserves the
text behind the English display summaries with its original UTF-8 SHA-256.

The archival serialization conversion itself made no model calls. Retrieval evaluation
retains escaped multilingual query fixtures so Chinese matching remains tested.

Current task-adjustment and English-answer acceptance is recorded separately in [the 2026-10-21 run](task-adjustments-20261021/acceptance.json), including two real GPT calls and isolated real-auth HTTP/browser checks. The route screenshots in that directory use synthetic acceptance tasks.
