# YOLO11n / YOLO11s 的 30 epoch 配对实验

负责人 A；2026-10-13 在已完成的 10 epoch 基线验证误差分析之后，授权分别训练 n / s 两个 30 epoch 模型。本文是实验协议，不代表训练完成或准确率验收。10 epoch 基线和其后端模型清单保留，不覆盖。

## 预先固定的协议

两组使用同一份 `Dataset/baseline10-config.json` 的输入、推理参数和训练参数，仅将 epoch 和 patience 都改为 30，并分别使用官方 COCO 预训练的 `yolo11n.pt` / `yolo11s.pt` 独立初始化。不能从 n 的 10 epoch 检查点续训到 30，也不能用 n 检查点初始化 s。各自中断后可以用该运行自己的完整恢复检查点继续到原定 30 epoch。

共同参数：seed 42、deterministic true、imgsz 640、batch 32、workers 4、device 0、amp false、cache false、fliplr 0、AdamW、lr0 0.001、lrf 0.01、warmup_epochs 1、close_mosaic 2。nbs 为 64，名义梯度累积为 2，名义有效 batch 为 64；warmup 期间累积步数由库调整。实际 batch 必须保持 32；OOM 自动缩小 batch 会被训练 guard 拒绝，不能静默变成不公平的比较。完整保留 best、last、latest / previous recovery 和实验日志。

两组运行名为 `yolo11n-rdd2022es-compare30-seed42` 和 `yolo11s-rdd2022es-compare30-seed42`。训练文件、数据 manifest、audit、split summary、预训练来源和哈希、准备计划及完整运行证据均放在忽略的 `Dataset/` 内。固定训练代码后应先提交，随后整个配对运行期间保持代码和输入不变；小型、去绝对路径的汇总可以由操作者复制到 `SystemCode/experiments/vision/` 供版本控制。

权重均来自 Ultralytics assets v8.3.0，n SHA-256 为 `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`，s 为 `85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5`。这些哈希是本次本地资产核验记录；s 下载时 GitHub 元数据没有发布 digest，不能称为发布方签名验证。工具只使用已有本地权重，缺失时明确失败，不下载。

## 生成、训练、验证和比较

从仓库根目录运行：

```powershell
# 所有资产须已准备；该步骤必须在两个 compare30 运行创建之前执行。
.venv/Scripts/python.exe SystemCode/model/compare_models.py prepare
# 生成 Dataset/compare30/{n-config.json,s-config.json,plan.json}；拒绝覆盖。
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/compare30/n-config.json
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config Dataset/compare30/n-config.json --split val
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/compare30/s-config.json
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config Dataset/compare30/s-config.json --split val
.venv/Scripts/python.exe SystemCode/model/compare_models.py compare
```

`prepare` 默认读取 baseline10 config、`Dataset/pretrained/download.json` 和 `Dataset/pretrained/download-yolo11s.json`。它冻结计划指纹、两个配置指纹、数据 YAML / manifest / audit / split summary 和预训练来源文件哈希；相同数据与完整增强 / 优化参数保留。已生成的计划不能重新生成覆盖，训练入口仍使用原来的 `train.py`。

比较工具先拒绝缺失 / 不匹配证据，再进行排序。必须同时具备恰好 30 个连续 epoch 的 results.csv、30 epoch recovery 身份及最新恢复权重哈希、四份保留检查点、成功的 val 状态、当前 best 权重对应的验证报告、八类源名称和模型清单。实际 args.yaml 和 `effective_training.json` 也须证明 batch 32、nbs 64、最终 train_end 及全部配置参数一致；运行时包、Python、训练来源哈希、代码 revision / dirty 状态、实际共同训练参数、验证图数和各类标注数必须相同。报告图数还须等于冻结的 val split summary。

`compare` 默认生成 `Dataset/compare30/summary.json`，拒绝覆盖已有摘要。摘要保留检查点哈希、输入指纹、实际训练参数指纹、运行来源、val 指标和建议的相对 `model_manifest.json` 路径，排除绝对路径和大文件。它不读取 `evaluation-test.json`，不执行测试集推理，不修改 `ROADGUARD_VISION_MANIFEST_PATH` 或现有后端运行。后端接入建议模型后仍需实际验收；所有模型状态保留 experimental。

## 预注册的选型规则

只按 validation mAP50-95 选高者；精确相等时按 validation mAP50 选高者。浮点值不先四舍五入。两项均精确相等时，才用同一 CPU 后端单图流程的 median latency 选低者。P / R / F1、逐类指标和业务烟雾测试是诊断证据，不改变该规则。不得利用 test 结果进行选型、调阈值或重训决策。

若需要延迟决胜，先用相同验证图片、CPU 线程数、已固定后端代码、推理参数和重复次数测量两组 best 权重；将证据保存于 `Dataset/` 并传入 `--cpu-latency PATH`。契约示例如下，哈希和数值必须来自实际测量：

```json
{
  "schema_version": "roadguard-compare30-cpu-latency-v1",
  "device": "cpu",
  "test_used": false,
  "protocol": {
    "pipeline": "backend_real_single_image",
    "source_split": "val",
    "image_set_sha256": "64位小写十六进制的固定输入列表指纹",
    "backend_source_sha256": "64位小写十六进制的后端来源指纹",
    "imgsz": 640, "conf": 0.25, "iou": 0.7,
    "cpu_threads": 4, "warmup": 2, "repeats": 5
  },
  "candidates": {
    "n": {"weights_sha256": "n的best.pt SHA256", "median_ms": 80.0},
    "s": {"weights_sha256": "s的best.pt SHA256", "median_ms": 100.0}
  }
}
```

以上 80 / 100 仅说明结构，不是测量结果。最少一次 warmup、三次正式重复；两个候选共享整个 protocol。精确指标平局但没有完整延迟证据、或延迟也相等时，工具拒绝任意指定胜者。

这是单 seed 的受限比较，不能估计训练方差或宣称统计显著优势。RDD2022ES 不是 Jurong 实拍，宽 / 深 / 下沉是视觉标签而非测量的工程尺寸；验证数值有效不等于业务准确率已达标，不校准自动接受阈值。选择完成后如另行授权最终 held-out test，应只评估已选模型一次，并将结果作为选型后的独立证据保留。

轻量验证命令（不安装 torch / Ultralytics，不使用 GPU）：

```powershell
.venv/Scripts/python.exe -m pytest SystemCode/tests/test_vision_comparison.py -q
```
