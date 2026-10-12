# Vision model - planned

The selected source is Juuso's RDD2022ES version 1 (`juusos/rdd2022es`). The eight source class IDs and names have been verified against the published metadata and the archive's `classes.txt`; see [the dataset and label audit](../../Miscellaneous/DATASET_AND_LABEL_AUDIT.md) and the shared [label schema](label_schema.json).

The archive directory contains 25,600 images and 25,599 annotation files, plus `classes.txt`. Two images lack matching annotations and one annotation lacks an image. The audit lists these exceptions. Nine original/mirror groups were inspected as a targeted content sample; full image/label validation and training splits remain pending. Source label names such as wide/sunken/deep do not establish measured severity or project priority.

The publisher's description says CC BY-SA 4.0, while its metadata says CC BY-NC-SA 4.0. Preserve this unresolved discrepancy in attribution and obtain clarification before redistribution or commercial use; do not copy the earlier single-license statement into new deliverables.

- Group original images with their `xmirror_` counterparts before splitting; check other duplicates and adjacent scenes separately.
- Quarantine the documented unmatched files rather than silently inventing negative labels. Record full class frequencies, preparation decisions, split proportions, seed and per-file provenance before training.
- Report class-level precision, recall, F1 and mAP@0.5 on held-out data.
- Evaluate confidence-gate acceptance quality separately from detector accuracy.
- Do not describe RDD2022ES as a dataset of Jurong roads.
- Mark any synthetic or demo predictions explicitly.

Dataset downloads, checkpoints and training outputs are excluded from Git. Add reproducible preparation, training and evaluation commands during implementation.
