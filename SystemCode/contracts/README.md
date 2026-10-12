# 固定契约样例

第 7 步新增 [planning/](planning/README.md)：使用 a-task-query-v1 的 10/15/20 任务、空队列和未知工时样例，按中央来源可复现。它们与下述原始 a-dto-v1 样例分开维护；在线查询入口、实际 HTTP 响应导出和 C 的知识包见 [B/C 交接说明](../../Miscellaneous/BC_HANDOFF.md)。

本目录由 A 维护，供 B/C 在业务服务尚未实现时联调。第一版 A DTO 的唯一说明位置是 [API_CONTRACT.md](../../Miscellaneous/API_CONTRACT.md)，可执行定义在 `backend/roadguard/schemas/`；此处不再维护一套字段说明。

`examples/manifest.json` 列出每份样例对应的 DTO，且对整个样例集声明 `is_demo: true`。各文件直接包含 DTO JSON，便于调用 Pydantic `model_validate_json` 或作为前端固定响应。巡检与任务自身继续携带 `is_demo`，错误样例在 `details` 中标明来源。Health/PlanningRevision 的固定字段结构不增加演示字段，其演示性质由文件名与 manifest 明确标识；它们不是运行中的数据库状态。

所有巡检、图片引用、检测和任务均为合成演示；`/demo-assets/synthetic-road.svg` 仅为示意资源地址，目前未实现该资源或图片服务。样例包含的 0.96、0.42、0.88 置信度并不定义分流阈值。`medium` / `P2` / 45 分钟及 `demo-unconfirmed-v1` 是演示值，不是已确认规则，不得将其直接复制成生产映射。

样例快照将一个 accepted 巡检关联到唯一演示任务，其他三个巡检没有任务；health/revision 都引用演示版本 1。没有实际创建任务、更新数据库版本、上传图片或运行检测。验证命令与依赖遵循后端 README 和仓库 pytest 配置。
