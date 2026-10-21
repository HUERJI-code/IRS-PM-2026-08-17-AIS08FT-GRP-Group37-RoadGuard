# RDD2022ES version 1 audit records

See the [dataset and label audit](../DATASET_AND_LABEL_AUDIT.md). These files record sources, full ZIP-directory inspection and targeted sample checks on 2026-10-12; they are not training data or model results.

| File | Purpose |
| --- | --- |
| [rdd2022es-v1-audit.json](rdd2022es-v1-audit.json) | Source version, licence discrepancy, directory counts, pairing anomalies, sample checks and unfinished items |
| [rdd2022es-v1-sample-manifest.json](rdd2022es-v1-sample-manifest.json) | Sizes, CRC32 and SHA-256 for 38 extracted archive members, calculated from original decompressed bytes |
| [label_schema.json](../../SystemCode/model/label_schema.json) | Verified label IDs 0–7, source names and project display names |

A full directory audit is not a full image/annotation-content audit. Samples deliberately cover all eight classes and anomalies; their proportions cannot estimate dataset-wide class distribution. CRC32 checks agreement between extracted content and directory records, without replacing SHA-256 of the complete archive.

Source: [Juuso / RDD2022ES](https://www.kaggle.com/datasets/juusos/rdd2022es). Publisher prose says CC BY-SA 4.0 while metadata says CC BY-NC-SA 4.0. This discrepancy remains unresolved; see the main document. Original images and labels are not included in the repository.
