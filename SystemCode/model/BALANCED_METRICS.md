# 八类均衡验证指标与离线置信度扫描

负责人 A。目标保持八个真实源类别，以同一个全局置信度尽量同时提高precision和recall，减少漏检。主指标匹配IoU固定0.5；IoU0.3仅作框位置容差的补充诊断，不替代主指标。四类family和class-agnostic也仅用于定位错误与亚类混淆诊断，不改变训练标签或API八类输出。

本工具只读取冻结 `Dataset/prepared/manifest.jsonl` 的全部1921张验证原图。读取manifest中的split元数据筛选val，打开图片/标签前拒绝镜像、排除样本、不一致split、非法ID及hash变化；不打开train/test图片或标签。该验证集已用于训练与选模，本次阈值与模型选择继续使用它；不能宣称新增独立holdout、测试集成绩或泛化验收。

GPU推理和离线扫描分成两个入口。一个模型/分辨率只推理一次；以后扫描不导入torch/Ultralytics、不会重新推理。仓库根目录示例（权重目录应按实际实验核对）：

```powershell
.venv/Scripts/python.exe SystemCode/model/balanced_metrics.py export --weights Dataset/runs/yolo11s-rdd2022es-compare30-seed42/weights/best.pt --run-name s30-best-640 --imgsz 640 --device 0
.venv/Scripts/python.exe SystemCode/model/balanced_metrics.py analyze --export Dataset/balanced-metrics/s30-best-640/export.json
```

API：`export_predictions(weights: Path, run_name: str, *, root=REPO_ROOT, imgsz=640, device='cpu') -> Path` 返回 `export.json`；`analyze_export(export_path: Path, analysis_name='sweep', *, root=REPO_ROOT) -> Path` 返回 `analyses/sweep/report.json`。`imgsz`只接受640、832或960；默认CPU，单GPU用字符串`'0'`。CLI保持完整1921张验证要求；测试注入fake model的执行记录明确为 `injected_test_model`，不能当作真实模型证据。

输出固定 `Dataset/balanced-metrics/<run-name>/`，此目录整体被Git忽略。新导出/分析名称只能用字母、数字、横线、下划线；拒绝已有目录覆盖及解析后越出存储边界的路径。仓库Dataset本身也不允许symlink/junction重定向到其他目录。运行失败保留状态与部分证据，不自动删除或续写；重试用新名。检查输入失败时不创建成功报告。

低置信度导出使用单图PIL RGB、`conf=0.001`、class-aware NMS `iou=0.7`、`max_det=100`、`batch=1`、`rect=true`、无augmentation。Ultralytics8.4.176用 `quantize=None` 请求FP32，不依赖已移除的 `predictor.args.half`。真实模型加载后检查全部参数/buffer finite；首张推理后检查实际backend `fp16=false`、floating tensors均为torch.float32且finite，以及真实设备与请求CPU/GPU一致。记录TF32与float32 matmul运行状态；GPU/CPU数值不保证逐位相同。导出记录分辨率、权重/manifest/data YAML/label schema/预测文件SHA256、源脚本SHA256、真实包版本和设备。离线扫描重新核对完成状态和这些输入，不接受低confidence验证器 `predictions.json` 的类别导出映射。

固定全局置信度网格：0.001、0.005、0.01、0.02、0.03、0.05、0.075、0.1、0.15、0.2、0.25、0.3、0.35、0.4、0.45、0.5、0.55、0.6、0.65、0.7、0.75、0.8、0.85、0.9、0.95。阈值过滤为 `confidence >= threshold`；不按类别另选阈值，也不重新NMS。低置信度下限与100检测上限限制候选范围，报告保留此局限。

每个匹配模式/IoU仅在每张图上调用一次confidence-ordered、class-aware、一对一贪心匹配，复用 `analyze_errors.match_detections`。最高confidence优先，同confidence保持原预测索引，最大IoU优先，标注索引打破IoU并列。较低confidence无法改变前面的匹配，因此按confidence排序累积TP/FP与标注支持数即可计算所有阈值，不需对25个阈值重复计算IoU。测试将前缀计数与逐阈值重新匹配逐类比对，覆盖重复、错类、定位误差和相等confidence。

报告包含主IoU0.5、补充IoU0.3下全部阈值的八类micro/macro/per-class TP/FP/FN、precision/recall/F1。Micro从八类总计数计算；macro为八类等权平均，undefined项平均时贡献0，逐类原值仍为null（例如无预测precision或无GT recall）。分别报告micro同时达到P≥0.7/R≥0.7与所选点全部八类是否达到要求；micro达标不意味着少数类达标。

选择规则在导出前固定：仅从主IoU0.5八类曲线选一个全局threshold，首先最大化micro `min(P,R)`，然后最大化八类macro F1，再最大化micro recall；完全并列保留升序网格中的首个threshold，与冻结实验plan一致。无预测/无GT的undefined micro指标不能赢过可定义指标。保存选择点与全部曲线，明确标记这是validation-tuned结果；不会修改模型manifest、后端threshold或激活新模型。

复现记录同时保留导出与离线分析时的 `balanced_metrics.py`、`analyze_errors.py`、`evaluate.py`、`train.py`、`checkpointing.py` 哈希，覆盖复用匹配与准备逻辑；不能仅凭Git HEAD推定dirty脚本完全一致。

诊断保持相同所选threshold，同时展示：

- class-agnostic一对一匹配衡量“是否定位到损伤”，再记录8×8源类别混淆矩阵，以及已定位对象中的正确八类/错误八类数量。它不能作为八类TP。
- 四类family仅将0/1、2/3、4/5、6/7临时合并做诊断，解释宽/普通、sunken/普通、deep/普通亚类混淆。它不能替换原八类指标。
- IoU0.3对框位置容差更宽，只能用于与IoU0.5并列解释；选阈值和目标是否达到始终看IoU0.5八类。

这些操作点指标不是官方mAP，也不校准工程严重度、自动接受门槛或业务规则。若主八类IoU0.5仍未同时达标，报告直接保留未达标结果，不能用更松的定位/family数字包装通过。

```powershell
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_balanced_metrics.py -q
```
