"""C-owned request/audit tables, created only by the shared migration entry."""
CHANGE_TABLES = {
    'assistant_changes': (
        "CREATE TABLE assistant_changes (change_id TEXT PRIMARY KEY, "
        "actor_id TEXT NOT NULL REFERENCES auth_users(user_id), client_key TEXT NOT NULL, "
        "payload_hash TEXT NOT NULL, record_json TEXT NOT NULL, UNIQUE(actor_id,client_key))",
        ('change_id', 'actor_id', 'client_key', 'payload_hash', 'record_json')),
    'assistant_change_events': (
        "CREATE TABLE assistant_change_events (event_id TEXT PRIMARY KEY, "
        "change_id TEXT NOT NULL REFERENCES assistant_changes(change_id), "
        "actor_id TEXT NOT NULL REFERENCES auth_users(user_id), action TEXT NOT NULL, "
        "created_at TEXT NOT NULL, details_json TEXT NOT NULL)",
        ('event_id', 'change_id', 'actor_id', 'action', 'created_at', 'details_json')),
}


def create_change_tables(connection):
    for sql, _ in CHANGE_TABLES.values():
        connection.execute(sql)
    connection.execute('CREATE INDEX assistant_changes_actor ON assistant_changes(actor_id)')
    connection.execute('CREATE INDEX assistant_change_events_request ON assistant_change_events(change_id,created_at)')


def validate_change_tables(connection):
    from roadguard.database import DatabaseStateError
    for table, (_, columns) in CHANGE_TABLES.items():
        info = connection.execute(f'PRAGMA table_info({table})').fetchall()
        if tuple(row[1] for row in info) != columns or tuple(row[1] for row in info if row[5]) != (columns[0],):
            raise DatabaseStateError('Assistant change schema is missing or incompatible.')
        if any(row[2] != 'TEXT' for row in info):
            raise DatabaseStateError('Assistant change column types are incompatible.')
    indexes = connection.execute('PRAGMA index_list(assistant_changes)').fetchall()
    if not any(tuple(r[0] for r in connection.execute(
            'SELECT name FROM pragma_index_info(?) ORDER BY seqno', (i[1],))) == ('actor_id', 'client_key')
               for i in indexes if i[2]):
        raise DatabaseStateError('Assistant change idempotency constraint is missing.')
