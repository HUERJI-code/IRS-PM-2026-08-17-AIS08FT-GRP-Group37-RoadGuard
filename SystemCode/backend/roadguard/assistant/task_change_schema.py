"""Durable task intent, affinity and audit storage (schema v6)."""
TASK_CHANGE_TABLES = {
    "assistant_task_changes": "CREATE TABLE assistant_task_changes (change_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES auth_users(user_id), client_key TEXT NOT NULL, payload_hash TEXT NOT NULL, record_json TEXT NOT NULL, UNIQUE(actor_id,client_key))",
    "assistant_task_change_events": "CREATE TABLE assistant_task_change_events (event_id TEXT PRIMARY KEY, change_id TEXT NOT NULL REFERENCES assistant_task_changes(change_id), actor_id TEXT NOT NULL REFERENCES auth_users(user_id), action TEXT NOT NULL, created_at TEXT NOT NULL, details_json TEXT NOT NULL)",
    "task_crew_constraints": "CREATE TABLE task_crew_constraints (task_id TEXT PRIMARY KEY REFERENCES tasks(task_id), crew_id TEXT NOT NULL, change_id TEXT NOT NULL REFERENCES assistant_task_changes(change_id))",
}
def create_task_change_tables(connection):
    for statement in TASK_CHANGE_TABLES.values():
        connection.execute(statement)

def validate_task_change_tables(connection):
    from roadguard.database import DatabaseStateError
    expected = {"assistant_task_changes": ("change_id", "actor_id", "client_key", "payload_hash", "record_json"), "assistant_task_change_events": ("event_id", "change_id", "actor_id", "action", "created_at", "details_json"), "task_crew_constraints": ("task_id", "crew_id", "change_id")}
    for table, columns in expected.items():
        info = connection.execute(f"PRAGMA table_info({table})").fetchall()
        if tuple(r[1] for r in info) != columns or tuple(r[1] for r in info if r[5]) != (columns[0],):
            raise DatabaseStateError("Task change schema is missing or incompatible.")
        if any(row[2] != "TEXT" for row in info):
            raise DatabaseStateError("Task change column types are incompatible.")

    indexes = connection.execute("PRAGMA index_list(assistant_task_changes)").fetchall()
    if not any(tuple(r[0] for r in connection.execute("SELECT name FROM pragma_index_info(?) ORDER BY seqno", (i[1],))) == ("actor_id", "client_key") for i in indexes if i[2]):
        raise DatabaseStateError("Task change idempotency constraint is missing.")
    required = {"assistant_task_changes": {("auth_users", "actor_id", "user_id")}, "assistant_task_change_events": {("auth_users", "actor_id", "user_id"), ("assistant_task_changes", "change_id", "change_id")}, "task_crew_constraints": {("tasks", "task_id", "task_id"), ("assistant_task_changes", "change_id", "change_id")}}
    for table, keys in required.items():
        actual = {(r[2],r[3],r[4]) for r in connection.execute(f"PRAGMA foreign_key_list({table})")}
        if not keys.issubset(actual):
            raise DatabaseStateError("Task change foreign keys are incompatible.")
