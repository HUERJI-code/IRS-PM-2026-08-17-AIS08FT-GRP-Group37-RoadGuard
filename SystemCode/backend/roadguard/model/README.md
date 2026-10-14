# 后端部署模型

当前部署权重已作为普通 Git 二进制文件纳入私有仓库。组员 clone/pull 后会自动取得下面的 `.pt` 文件，无需 Git LFS 或单独下载：

```text
SystemCode/backend/roadguard/model/
├── README.md
└── roadguard-yolo11s-single-v1.pt
```

后端默认加载这个固定文件，不需要修改代码、设置模型环境变量或运行安装脚本。新环境仍需按[模型接入说明](../../../../Miscellaneous/MODEL_RELEASE_AND_BACKEND.md)安装后端与视觉依赖；拉取后启动或重启后端，在巡检上传接口选择 `mode: "real"`。如果 PyCharm 中曾设置 `ROADGUARD_VISION_MANIFEST_PATH`，移除旧覆盖值以使用默认配置。

[默认模型清单](../../../model/releases/roadguard-single-v1.json)保存权重路径、SHA-256、八类标签和推理参数。加载器按仓库位置定位文件，与终端或 PyCharm 工作目录无关；首次真实推理校验权重后加载，之后复用内存中的模型。文件缺失或校验失败时返回 `503 detector_unavailable`，修复后重启；不会自动回退到 Dataset 中的旧模型。

- 权重大小：19,218,837 bytes。
- SHA-256：`464f5f2af596140f71583e974146f10819765adf851bc8ac73198b7fa7f51488`。
- 单框响应、0.20 推理过滤阈值、主框置信度达到 0.60 自动建任务的现有逻辑不变。
- 此目录只放部署用权重；训练代码仍在 `SystemCode/model/`，原始数据和训练保存点仍在根目录 `Dataset/`。
- 只有这一份指定权重获准进入 Git；其他 `.pt/.pth/.onnx` 和整个 Dataset 继续排除。CI 校验指定文件的大小、SHA-256 和默认清单，拒绝错误文件或 LFS 指针。
- [vision-single-v1 Release](https://github.com/HUERJI-code/IRS-PM-2026-08-17-AIS08FT-GRP-Group7-RoadGuard/releases/tag/vision-single-v1) 保留为备份下载渠道。可选的 `SystemCode/model/install_released_model.py --file <下载文件路径>` 也会校验并安装到此目录，正常 clone/pull 无需执行。

本次改变部署位置和交付方式，模型版本与识别效果不变。
