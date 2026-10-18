"""Auth tables are migrated only by the shared Database entrypoint."""

AUTH_TABLES = {
    "auth_users": "CREATE TABLE auth_users (user_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, "
                  "display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('inspector','crew','dispatcher')), "
                  "crew_id TEXT, password_hash TEXT NOT NULL, enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), "
                  "created_at INTEGER NOT NULL, CHECK((role='crew' AND crew_id IS NOT NULL) OR (role!='crew' AND crew_id IS NULL)))",
    "auth_sessions": "CREATE TABLE auth_sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES auth_users(user_id), "
                     "expires_at INTEGER NOT NULL)",
    "auth_login_limits": "CREATE TABLE auth_login_limits (limit_key TEXT PRIMARY KEY, window_start INTEGER NOT NULL, attempts INTEGER NOT NULL)",
    "inspection_owners": "CREATE TABLE inspection_owners (inspection_id TEXT PRIMARY KEY REFERENCES inspections(inspection_id), "
                         "user_id TEXT NOT NULL REFERENCES auth_users(user_id))",
    "auth_audit": "CREATE TABLE auth_audit (event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES auth_users(user_id), "
                  "action TEXT NOT NULL, resource_id TEXT NOT NULL, request_id TEXT NOT NULL, crew_id TEXT, plan_id TEXT, created_at INTEGER NOT NULL)",
}


def create_auth_tables(connection):
    for statement in AUTH_TABLES.values():
        connection.execute(statement)
    connection.execute("CREATE INDEX auth_sessions_user ON auth_sessions(user_id)")
    connection.execute("CREATE INDEX auth_audit_resource ON auth_audit(resource_id,crew_id,action)")


def validate_auth_tables(connection):
    from roadguard.database import DatabaseStateError
    expected = {
        "auth_users": ("user_id", "username", "display_name", "role", "crew_id", "password_hash", "enabled", "created_at"),
        "auth_sessions": ("token_hash", "user_id", "expires_at"),
        "auth_login_limits": ("limit_key", "window_start", "attempts"),
        "inspection_owners": ("inspection_id", "user_id"),
        "auth_audit": ("event_id", "user_id", "action", "resource_id", "request_id", "crew_id", "plan_id", "created_at"),
    }
    for name, columns in expected.items():
        info = connection.execute(f"PRAGMA table_info({name})").fetchall()
        if tuple(row[1] for row in info) != columns or tuple(row[1] for row in info if row[5]) != (columns[0],):
            raise DatabaseStateError("Authentication schema is missing or incompatible.")
