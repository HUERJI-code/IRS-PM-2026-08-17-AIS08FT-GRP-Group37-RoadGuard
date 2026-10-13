# RDD2022ES v1 本地准备

负责人 A；第 8 步数据接口。下载器由项目负责人执行，准备脚本不访问网络。
将固定第 1 版完整 ZIP 放到仓库 `Dataset/downloads/rdd2022es-v1.zip` 后，
在仓库根目录使用已安装 Pillow 的 Python 执行：

```powershell
python SystemCode/model/data_pipeline.py prepare
```

所有大文件及生成清单保留在被 Git 忽略的 `Dataset/`。脚本计算下载包 SHA-256，
核对完整包固定 SHA-256 `3ceb9de3b7ca7083379e4fc62748bafcda0a82d1baf4627cf87891c9595fa775`
及 2,611,933,018 字节，安全解压至 `Dataset/raw/rdd2022es-v1/`，核对固定版目录数量和八类名称，
逐张完整解码 JPEG、核对镜像关系、逐行核对类别／有限数值／正框宽高及边界。
归一化边界容差 `1e-6` 只用于发布者六位小数的舍入。原文件不修正、不删除。
已知缺失标注 `Czech_001003` 整组隔离；`India_001032.txt` 保留并记录为孤立标注。
其他缺失、坏图、非法标注或镜像关系错误将保存失败审计并返回非零状态，不发布 YAML。
空标注仅表示没有标注框，不证明道路安全，也不新增“安全道路”训练类别。

2026-10-13 首次真实全量运行已完成 25,600 次完整图片解码尝试；发现且仅报告
`India_000430.jpg` 的 EXIF 方向为 8、`India_004098.jpg` 的方向为 3。
两张原图及其镜像均为 720×720，镜像方向为 1。原图标签是否按 EXIF 旋转后的
图像坐标标注尚未核实；项目负责人决定原始和镜像整组隔离，原文件不改动。
脚本只允许下列固定 v1 成员的 SHA-256 及方向都匹配时以
`exif_orientation_unverified_labels` 原因排除；仍完整解码图片及校验标注。
未知方向或已知成员内容变化仍使准备失败。首轮失败审计由负责人保留至
`Dataset/audits/initial-exif-failure/`，后续完整重跑结果另行记录。

| 成员 | EXIF 方向 | 固定 SHA-256 |
| --- | ---: | --- |
| `India_000430.jpg` | 8 | `01c4ef927c8193a209e1169f8bc937ad16764c1b2d756ba0a5c9d7332ea3fa9c` |
| `xmirror_India_000430.jpg` | 1 | `c4bfebccb2f4a6bda5a9891c18d6a2bcc43689395e2a634cd1c118ae15c6c167` |
| `India_004098.jpg` | 3 | `219984707789be5cab1418ae6804227487b08b1eae5b158cf88dc44b26e73c2a` |
| `xmirror_India_004098.jpg` | 1 | `b3f2acdf5013819d14f6b9f503a3dfa2ae155eddee6b36aa0424e8d48f9feb35` |

先将原图与 `xmirror_`、字节 SHA-256 重复、解码像素重复归组，再对原图使用
镜像感知 64 位 dHash BK 树筛选近重复候选（距离最多 4），以 16×16 RGB 缩略图
RMSE ≤6 的保守标准合并；接受的近重复边保存在 `audit.json`。
这些启发式可能过度分组或漏掉相邻场景，不能声称全部近重复／相邻帧已清除。
未获得拍摄序列或位置元数据；评估仍有未识别场景相关性的限制。

按组合并后的国家集合分层，固定种子 42，组级比例 70/15/15，以最大余数法分配，
属于项目暂定方案。跨国家重复组形成自己的国家集合层，不拆组。
训练使用原图及已有镜像；验证／测试仅使用原图；训练必须设置 `fliplr=0.0`。
小国家集合层可能没有验证／测试组，应检查实际分布；不保证每类均匀分层。

输出 `Dataset/prepared/`：

- `data.yaml`：可被 YAML 解析，八类 `names` 为共享字典中的来源英文名。
- `images/{train,val,test}` 与 `labels/{train,val,test}`：优先硬链接，失败时复制并核对 SHA。
- `manifest.jsonl`：每张原始图片的来源路径、国家、原图组、最终重复组、SHA、标签框、
  实际 split、分配 split 和排除原因。孤立标注在审计 `exclusions` 中记录。
- `audit.json`：下载哈希、全量验证、隔离、重复分组及其限制、完整类别统计和防泄漏断言。
- `split_summary.json`：每划分图片数／组数／国家／空标注／类别框数和含类别的图片数。

准备目录不能被覆盖；需要重跑时先由操作者保存旧目录，再使用新的 Dataset 根目录
（`--archive`、`--dataset-root`，CLI 限制在仓库 `Dataset/` 之内），或将旧 prepared 目录移到其他名称。
原始和准备后文件因硬链接共享内容，训练工具必须仅只读访问，不能修改标注／图片。
脚本可复用已有 raw，但每个已有成员重新与 ZIP 内容比较，不信任旧解压标记。

本数据不是 Jurong 实拍；来源及 BY-SA 正文／BY-NC-SA 元数据差异继续以
[数据集核验](../../Miscellaneous/DATASET_AND_LABEL_AUDIT.md)为准。
测试命令 `python -m pytest SystemCode/tests/test_data_pipeline.py -q` 使用合成 ZIP，
不下载真实数据或训练模型。
