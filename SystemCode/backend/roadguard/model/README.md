# Backend deployment model

The deployment weights are a regular Git binary in this private repository. Clone/pull retrieves the `.pt` file automatically, without Git LFS or a separate download:

```text
SystemCode/backend/roadguard/model/
├── README.md
└── roadguard-yolo11s-single-v1.pt
```

The backend loads this fixed file by default; no code changes, model environment variables or installation script are needed. New environments still need backend and vision dependencies from the [model integration guide](../../../../Miscellaneous/MODEL_RELEASE_AND_BACKEND.md). Start or restart the backend after pulling, and select `mode: "real"` on inspection upload. Remove an old `ROADGUARD_VISION_MANIFEST_PATH` override in PyCharm to use the default.

The [default model manifest](../../../model/releases/roadguard-single-v1.json) records the weights path, SHA-256, eight labels and inference parameters. The loader resolves paths from the repository location independently of terminal/PyCharm working directories. It verifies and loads weights on first real inference, then reuses the in-memory model. Missing files or failed verification return `503 detector_unavailable`; restart after repair. It never falls back automatically to older models in Dataset.

- Size: 19,218,837 bytes.
- SHA-256: `464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`.
- Existing single-box responses, 0.20 inference filtering and automatic task creation at primary confidence 0.60 remain unchanged.
- This directory contains deployment weights only. Training code remains in `SystemCode/model/`; raw data and training checkpoints remain in root `Dataset/`.
- Only this specified weight file is authorized in Git. Other `.pt/.pth/.onnx` files and all Dataset content remain excluded. CI checks size, SHA-256 and the default manifest, rejecting incorrect files and LFS pointers.
- The [vision-single-v1 Release](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group37-RoadGuard/releases/tag/vision-single-v1) remains a backup download channel. Optional `SystemCode/model/install_released_model.py --file <downloaded-file-path>` also verifies and installs here; normal clone/pull does not require it.

This changes deployment location and delivery only; model version and detection quality are unchanged.
