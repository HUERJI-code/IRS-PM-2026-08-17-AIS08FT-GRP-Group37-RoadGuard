# Vision model - planned

The proposed dataset is RDD2022ES, used to learn road damage and basic severity labels. Record its source, license, downloaded version, label mapping and split procedure before training.

- Keep original images and their mirrored counterparts in the same split.
- Report class-level precision, recall, F1 and mAP@0.5 on held-out data.
- Evaluate confidence-gate acceptance quality separately from detector accuracy.
- Do not describe RDD2022ES as a dataset of Jurong roads.
- Mark any synthetic or demo predictions explicitly.

Dataset downloads, checkpoints and training outputs are excluded from Git. Add reproducible preparation, training and evaluation commands during implementation.
