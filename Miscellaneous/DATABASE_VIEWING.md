# 查看 RoadGuard 数据库

本项目使用 SQLite，默认文件是仓库中的 `SystemCode/backend/data/roadguard.sqlite3`。无需独立启动 MySQL/PostgreSQL 服务。PyCharm 运行配置若设置了 ROADGUARD_DB_PATH，应查看该覆盖路径；相对路径按仓库根目录解析。

## 先通过 Swagger 查询

后端启动后打开 `http://127.0.0.1:8000/docs`：

| 接口 | 用途 |
| --- | --- |
| GET /api/v1/inspections | 巡检列表，默认包含各状态；每条最多一个展示框 |
| GET /api/v1/inspections/{inspection_id} | 一次巡检的完整业务详情，包括模型、规则、审核历史；原始全部候选仅存于数据库 |
| GET /api/v1/tasks?status=all | 全部状态的任务列表，支持分页；默认不传 status 时只返回 active |
| GET /api/v1/tasks/{task_id} | 单个任务及其修改历史 |
| GET /api/v1/tasks/snapshot | 全部活动任务与同一事务下的 input_revision，供规划使用 |

新上传只返回 inspection_id、status、detection、task_id。把返回的 ID 填入详情接口，点击 Execute 即可。

## 在 PyCharm 打开数据库文件

如果你的 PyCharm 提供 Database 工具窗口：

1. 打开 **View → Tool Windows → Database**。
2. 点击 **+ → Data Source → SQLite**。
3. 在 File 选择当前项目的 `SystemCode/backend/data/roadguard.sqlite3`，连接已有文件。
4. 如果提示缺驱动，点击 Download missing driver files；然后 Test Connection → OK。
5. 展开数据库表，双击 inspections 或 tasks 查看数据；新增记录后刷新表格。

这使用 PyCharm 的 Database Tools 功能；若当前环境没有这个窗口，可直接用上面的 Swagger，无需为查看数据改后端。[JetBrains SQLite 连接说明](https://www.jetbrains.com/help/pycharm/sqlite.html)、[Database 快速入门](https://www.jetbrains.com/help/pycharm/quick-start-with-database-functionality.html)。

## 四张表分别是什么

| 表 | 内容 |
| --- | --- |
| inspections | 巡检 ID、状态、版本、创建时间；record_json 存完整原始检测/图片引用/审核记录，policy_json 存本次冻结的业务规则 |
| tasks | 任务 ID、来源巡检、状态、版本、创建时间；record_json 存类型、优先级、工时及修改历史 |
| operation_keys | 上传/审核/修改的幂等请求键及关联资源，防重复创建或执行 |
| infra_metadata | 数据库结构版本与全局规划输入版本 input_revision |

图片本体保存在数据库旁边的 uploads 目录（除非覆盖 ROADGUARD_UPLOAD_PATH），数据库保存图片地址，不把图片当作二进制字段存储。模型权重另在 Dataset/models 中。

业务对象的完整字段存储为 record_json，所以表格中不会每个业务字段都单独显示一列。可以查看该单元格的 JSON，或者用下面的只读 SQL 提取想看的字段。

## 常用只读 SQL

最近 20 条巡检：

```sql
SELECT inspection_id, status, created_at,
       json_extract(record_json, '$.mode') AS mode,
       json_extract(record_json, '$.task_id') AS task_id
FROM inspections
ORDER BY created_at DESC
LIMIT 20;
```

最近 20 条任务：

```sql
SELECT task_id, status,
       json_extract(record_json, '$.damage_label') AS damage_label,
       json_extract(record_json, '$.priority') AS priority,
       json_extract(record_json, '$.service_minutes') AS service_minutes
FROM tasks
ORDER BY created_at DESC
LIMIT 20;
```

手动查看用 SELECT；修改任务、完成、取消等通过 API 操作，使规则快照、修改历史和 input_revision 一起更新。直接改表格只改一部分字段会破坏这些一致性约定。运行数据库与上传图片均被 Git 忽略，不上传 GitHub。
