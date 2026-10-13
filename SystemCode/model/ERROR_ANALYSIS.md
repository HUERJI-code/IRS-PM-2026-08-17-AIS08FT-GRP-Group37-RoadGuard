# 验证集操作点错误分析

负责人 A。`analyze_errors.py` 只分析冻结的 `Dataset/prepared/manifest.jsonl` 中全部 1921 张非镜像验证原图。读取完整 manifest 元数据以筛选 `split=val`，只打开验证图片和标签；不读训练或测试图片、标签，也不选择测试集阈值。数据 YAML 必须保留 preparation 布局和八类字典；原图和原标签只读，逐张 SHA256 与 manifest 核对，标签数值与 manifest boxes 一致。

在仓库根目录指定已经完成训练的本地权重和全新输出名。例如十轮基线（具体运行目录以实际本地记录为准）：

```powershell
.venv/Scripts/python.exe SystemCode/model/analyze_errors.py --weights Dataset/runs/yolo11n-rdd2022es-baseline10-seed42/weights/best.pt --run-name baseline10-val-errors --device 0
```

`--device cpu` 为默认，单 GPU 用 `--device 0`。运行前用训练记录核对权重目录；不存在权重直接失败，不下载模型。输出固定为忽略的 `Dataset/error-analysis/<run-name>/`，不覆盖已有目录、拒绝路径穿越和解析后越出数据目录的链接。失败保留 `status.json` 和已生成部分证据，不发布成功报告；重试必须使用新名。

本工具逐图用 PIL RGB 调用真实 `model.predict`，以实际 `model.names` 校验 0～7 源类别。默认 `conf=0.25`、NMS `iou=0.7`、`max_det=100`、`imgsz=640`、`batch=1`、`half=false`、`rect=true`、无测试时增强、class-aware NMS。可以显式调整 `--conf` 和 `--match-iou`，但必须使用新运行名；默认诊断匹配 IoU 为 0.5。报告记录实际设备、包版本和输入权重/manifest/data YAML SHA256，以及分析脚本 SHA256。GPU和CPU数值不保证逐位一致；稳定排序、固定种子和样例选择不代表GPU计算完全确定。

后端 API 同样用单图 PIL RGB、CPU、`max_det=100` 和模型清单里的 `conf/iou/imgsz`。默认清单参数应另行核对；工具使用GPU时明确记录与API设备差异。验证器 `predictions.json` 来自低置信度 multi-label 验证和类别导出映射，不能作为此工具的直接预测输入。这里的 P/R 是固定部署实验操作点，不是验证曲线最大平均F1位置，也不是官方 mAP；不能宣称阈值已校准或自动接受已达标。

匹配按预测置信度降序（并列使用原预测索引）逐一寻找未匹配同类标注，选最大 IoU（并列标注索引），IoU达到阈值记TP。每个预测/标注至多一次TP；未匹配预测记FP，未匹配标注记FN。混淆/定位问题仍同时产生FP和FN。诊断关联可复用对象，仅解释错误，不改变TP的一对一关系：

- FP先检查已匹配同类标注的高IoU重复，再检查高IoU异类混淆，再检查同类 `0.1 ≤ IoU < match_iou` 定位问题，其余为背景。
- FN先检查高IoU异类预测混淆，再检查同类低IoU定位，其余为漏检。
- 背景FP可能提示标签遗漏，也可能是模型误检。此工具不能确认标注错误，不会修改数据。

`report.json` 包含八类TP/FP/FN、precision/recall及错误种类计数，无预测或无标注分母时相应指标为null。`image-results.jsonl` 保存全部验证图的真值、原图像素预测和诊断对象索引。`sample_selection` 先轮转FP/FN及错误类别，再覆盖类别/国家，并用固定seed哈希排序选择最多40张独立图片；这是定向错误审核样例，不是随机质量估计。

`samples/*.jpg` 左侧为冻结标签，右侧为预测；绿色TP、红色FN、橙色FP，并显示类别ID/源名、对象索引、置信度和诊断类型。`contact-sheet-*.jpg` 每张最多12个对照，用于快速筛查，个别框文字细节请打开独立1200×600对照图。将疑似漏标或类别歧义作为人工审核候选，不能据此直接改标签。

普通CI无需torch/GPU；测试用明确标记的假模型，覆盖置信度顺序/并列、边界IoU、一对一重复、错误类别、定位、空场景、完整验证数、镜像/路径拒绝、真实输入摘要核验、样例分层和假模型端到端产物。

```powershell
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_error_analysis.py -q
```
