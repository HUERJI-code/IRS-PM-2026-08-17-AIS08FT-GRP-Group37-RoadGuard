# Viewing the RoadGuard database

The project uses SQLite, by default at `SystemCode/backend/data/roadguard.sqlite3`. No separate MySQL/PostgreSQL server is needed. If a PyCharm run configuration sets ROADGUARD_DB_PATH, inspect that overridden path; relative paths resolve against the repository root.

## Query through Swagger first

After starting the backend, open `http://127.0.0.1:8000/docs`:

| Endpoint | Purpose |
| --- | --- |
| GET /api/v1/inspections | Inspections across all statuses by default; at most one display box per record |
| GET /api/v1/inspections/{inspection_id} | Full business details, model, rules and review history; all raw candidates remain database-only |
| GET /api/v1/tasks?status=all | Paginated tasks in all statuses; omitting status defaults to active only |
| GET /api/v1/tasks/{task_id} | One task and its change history |
| GET /api/v1/tasks/snapshot | All active tasks and input_revision from one transaction, for planning |

New uploads return only inspection_id, status, detection and task_id. Enter the returned ID in the detail endpoint and select Execute.

## Open the database in PyCharm

If your PyCharm has the Database tool window:

1. Open **View → Tool Windows → Database**.
2. Select **+ → Data Source → SQLite**.
3. Select the existing `SystemCode/backend/data/roadguard.sqlite3` file in this project.
4. If prompted, select Download missing driver files, then Test Connection → OK.
5. Expand tables and double-click inspections or tasks. Refresh after new records are added.

This uses PyCharm Database Tools. If unavailable, use Swagger above without changing the backend. [JetBrains SQLite connections](https://www.jetbrains.com/help/pycharm/sqlite.html), [Database quick start](https://www.jetbrains.com/help/pycharm/quick-start-with-database-functionality.html).

## The four tables

| Table | Contents |
| --- | --- |
| inspections | ID/status/revision/creation time; record_json contains complete raw detections/image references/review, policy_json the frozen rules |
| tasks | ID/source inspection/status/revision/creation time; record_json contains type, priority, duration and change history |
| operation_keys | Idempotency keys and associated resources for upload/review/change, preventing duplicate creation/execution |
| infra_metadata | Database schema version and global planning input_revision |

Images live in uploads beside the database unless ROADGUARD_UPLOAD_PATH overrides it. The database stores references rather than binary image fields. Default deployment weights are separately in SystemCode/backend/roadguard/model.

Complete business objects are stored in record_json, so individual business fields are not separate table columns. Inspect the JSON cell or extract fields with read-only SQL.

## Common read-only SQL

Latest 20 inspections:

```sql
SELECT inspection_id, status, created_at,
       json_extract(record_json, '$.mode') AS mode,
       json_extract(record_json, '$.task_id') AS task_id
FROM inspections
ORDER BY created_at DESC
LIMIT 20;
```

Latest 20 tasks:

```sql
SELECT task_id, status,
       json_extract(record_json, '$.damage_label') AS damage_label,
       json_extract(record_json, '$.priority') AS priority,
       json_extract(record_json, '$.service_minutes') AS service_minutes
FROM tasks
ORDER BY created_at DESC
LIMIT 20;
```

Use SELECT for manual inspection. Modify, complete and cancel through APIs so frozen rules, history and input_revision update together. Editing only some table fields breaks these consistency rules. Runtime databases/uploads are Git-ignored and must not go to GitHub.

## Handling database is locked

A viewer retaining an unfinished query transaction may hold a read lock even after SELECT. Under SQLite's default rollback-journal mode this can block another connection's write commit; an unfinished write transaction also blocks writes. [SQLite transactions](https://www.sqlite.org/lang_transaction.html), [locking](https://www.sqlite.org/lockingv3.html).

1. In PyCharm Database, right-click the RoadGuard data source and select **Disconnect**, leaving the IDE/project open. Inspect any uncommitted changes before choosing to commit or discard them.
2. Stop the backend instance that failed startup and restart with its original Run configuration. Wait for `Application startup complete` before opening Swagger; `Uvicorn running` alone does not confirm application startup, especially with `--reload`.
3. End queries and disconnect after viewing data to avoid long transactions; do not start duplicate backend instances.

Startup validation for the current schema now uses a read-only transaction. Creation/migration still uses writes. This avoids unnecessary write-lock contention during normal restart but neither bypasses external exclusive locks nor removes external transaction blocking of uploads/task changes.

Do not delete `roadguard.sqlite3` or its `-journal`, `-wal`, `-shm` files to fix locks: they may contain data awaiting recovery.
