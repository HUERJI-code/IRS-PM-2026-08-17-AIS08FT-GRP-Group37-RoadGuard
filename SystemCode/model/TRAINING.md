# 第 8 步：真实视觉训练、恢复与评估

负责人 A。以下是可复现入口，不是已经取得的准确率结论。八类名称保持 `label_schema.json` 的原始顺序。RDD2022ES 第 1 版不是 Jurong 道路影像；来源许可证冲突继续按数据核对文档保留。

使用仓库现有 `.venv`，正式本地训练环境是 Windows / Python 3.12 / RTX 5090。先按官方 CUDA 12.8 索引安装 PyTorch，再安装可选视觉依赖；普通后端 CI 不安装 torch，测试通过依赖注入检验恢复和清理契约。

```powershell
.venv/Scripts/python.exe -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python.exe -m pip install -r SystemCode/model/requirements-vision.txt
```

运行前用 `data_pipeline.py` 完成全量内容核验和分组划分。数据、官方预训练 `yolo11n.pt`、日志、权重、指标、工具缓存均保存在忽略的 `Dataset/` 下。预训练权重必须由操作者明确下载并保留来源和 SHA256；训练和后端不自动下载模型。训练入口在首次导入 Ultralytics 前设置离线环境、禁止自动安装，并关闭同步与云日志集成。

配置校验将解析后的 `dataset_root` 限制在仓库 `Dataset/` 子树内。数据 YAML 本身和其中的 `path`、`train`、`val`、可选 `test` 路径同样必须留在该存储范围；现有 preparation／smoke 的绝对 `path` 和相对 image 目录直接支持。`path` 也可省略，此时使用 YAML 所在目录。相对 `path` 因依赖 Ultralytics 全局 datasets 设置而拒绝。为保持普通 CI 无额外解析依赖，仅接受生成器使用的逐行顶层键、JSON 标量／数组与普通本地目录字符串；拒绝复杂 YAML、重复／未知键、download 指令和间接 image-list 文件，并核验八类名称。路径解析检查能拒绝指向范围外的 symlink／junction；它不重新执行全量图像内容审计。

`training.example.json` 是初始正式运行上限：30 epoch、640 像素、batch 16、seed 42、patience 10。`cache=false` 避免图像解码缓存，`fliplr=0` 避免重复镜像增强，AdamW 固定优化器。初始 `workers=0` 保守适配 Windows；经过 smoke 可改为 2 或 4。`amp=false` 避免库的自动 AMP 检查引入辅助权重下载。修改参数必须用新的运行名；恢复时配置哈希须完全一致。

先用 `make_smoke.py` 从已通过全量审计的冻结划分创建 64 张训练图和 32 张验证图的恢复测试子集，不读取测试集。生成配置为 2 epoch、320 像素、batch 8、workers 0，保留八类字典；不要将它的指标写成全量模型指标。正式运行配置另存于 `Dataset/`。已存在的 smoke 数据/配置不覆盖。

```powershell
.venv/Scripts/python.exe SystemCode/model/make_smoke.py
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/smoke-config.json --stop-after-epoch 1
# 上条故意在完成并保存一个 epoch 后退出，退出码 75。
.venv/Scripts/python.exe SystemCode/model/train.py --config Dataset/smoke-config.json --resume Dataset/runs/recovery-smoke/weights/resume-latest.pt
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config Dataset/smoke-config.json --split val
.venv/Scripts/python.exe SystemCode/model/train.py --config SystemCode/model/training.example.json
```

每个已完成 epoch 的 `on_model_save` 保存完整恢复状态，通过同目录临时文件、flush/fsync 和原子 replace 发布 `weights/resume-latest.pt`，上一份保留为 `resume-previous.pt`。Windows 保证文件替换发布边界；突然断电的最终持久性仍取决于文件系统与硬件。中途退出会丢失当前未完成 epoch，从最近完成的 epoch 恢复。最新损坏时必须显式指定 previous，禁止悄悄重新训练。

恢复检查配置、数据 YAML、manifest、预训练权重 SHA256 和 Python/主要包版本。完整状态包含 epoch、原精度 optimizer、AMP scaler、scheduler、实时模型、EMA、early-stop 状态、Python/NumPy/torch/CUDA RNG 和 dataloader generator。Ultralytics 自身恢复先运行；`on_pretrain_routine_end` 再恢复实时状态。`resume_verified.json` 记录下一 epoch 与 optimizer state 数量。多 worker 的预取与 GPU 运算意味着不保证中断运行与连续运行逐位相同。

Ultralytics 完成训练时会移除 `last.pt`／`best.pt` 的优化器；这两份用于推理和选优，独立 recovery 权重不会被移除状态。已完成配置的最后 epoch 不允许用 resume 重新开始；应直接评估。默认不产生每 epoch 的历史副本，只保留 last、best、latest、previous 和相关证据。

```powershell
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config SystemCode/model/training.example.json --split val
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config SystemCode/model/training.example.json --split test
# 清理预览；引用既有成功验证报告可避免再运行验证。
.venv/Scripts/python.exe SystemCode/model/evaluate.py --config SystemCode/model/training.example.json --cleanup --existing-report Dataset/runs/yolo11n-rdd2022es-v1-seed42/evaluation-val.json
# 人类已授权清理时添加 --apply-cleanup。
```

评估输出 `evaluation-val.json`／`evaluation-test.json`，含整体和八类 P/R/F1/mAP50/mAP50-95、标注数量、九行九列的混淆矩阵（含背景）以及混淆类别例子。`evaluation-{split}/val_batch*.jpg` 是有限批次的预测与标签对照图，`predictions.json` 保存预测。缺失 ground truth 的类别指标为 null，并标记未评估。P/R/F1 使用库的最大平均 F1 曲线位置，测试集上此值仅用于描述，不能据此调整部署置信度；部署 `conf=0.25` 是明确的实验参数，不是已校准自动接受阈值。指标曲线收集固定 `conf=0.001,iou=0.7`。

数值检查通过只表示名称、样本和有限范围指标有效，`accuracy_acceptance=not_defined_not_claimed`；不会把低准确率或缺失类别包装成业务验收通过。val 成功后导出 `model_manifest.json`，状态始终 `experimental`，包含本地权重路径、SHA256、八类原名、模型／数据版本、数据 manifest 哈希、推理参数和验证报告位置。后端按共享 `roadguard-model-v1` 契约验证；未校准的真实结果保留人工复核。

清理默认 dry-run，且仅在训练结束、当前 best 权重验证成功、manifest 未变时允许。白名单是 `Dataset/prepared/labels/{train,val,test}.cache` 和 `Dataset/prepared/images/{train,val,test}/*.npy`；遇到 symlink/junction 路径拒绝。原始压缩包、源图片／标注、划分、manifest、audit、best/last/recovery、模型清单、日志、评估和指标均不属于清理范围。清理计划和实际释放字节写入运行目录。

运行元数据记录实际包版本、Git HEAD、dirty 标志和训练／数据脚本 SHA256。未提交代码的训练不能被描述为由 HEAD 完全复现；交付时同时保留来源哈希与提交后的代码。真实训练结果由运行目录证据填写，不能根据 smoke 或假对象测试编造正式指标。

实现依据：[Ultralytics Trainer 源码](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/engine/trainer.py)、[验证源码](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/models/yolo/detect/val.py)、[PyTorch 版本安装说明](https://pytorch.org/get-started/previous-versions/)。本地固定库版本的源文件是恢复 callback 和评估接口的最终核对依据。

2026-10-13 实际完成上述恢复测试及全量 10 epoch 基线，详见[验收记录](../../Miscellaneous/STEP8_VISION_ACCEPTANCE.md)。30 epoch 示例不是本次已运行的配置。实际配置、每类指标、检查点摘要及局限见[实验摘要](../experiments/vision/step8_baseline_summary.json)。
