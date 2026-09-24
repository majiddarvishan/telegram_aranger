import sqlite3


SCHEMA_VERSION = 4


def get_db(db_file: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def initialize_database(db_file: str) -> None:
    conn = get_db(db_file)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS telegram_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_user_id INTEGER NOT NULL,
            phone_number TEXT,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            encrypted_session BLOB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, telegram_user_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS web_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_web_sessions_token_hash ON web_sessions(token_hash);
        CREATE INDEX IF NOT EXISTS idx_web_sessions_user_id ON web_sessions(user_id);
        CREATE TABLE IF NOT EXISTS web_login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_web_login_attempts_username_time
            ON web_login_attempts(username, attempted_at);
        CREATE TABLE IF NOT EXISTS message_tags (
            telegram_account_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL DEFAULT 0,
            message_id INTEGER NOT NULL,
            tags TEXT,
            PRIMARY KEY(telegram_account_id, chat_id, message_id),
            FOREIGN KEY(telegram_account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS telegram_dialog_cache (
            telegram_account_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            title TEXT NOT NULL,
            chat_type TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            peer_access_hash INTEGER,
            peer_type TEXT NOT NULL DEFAULT '',
            fetched_at TEXT NOT NULL,
            PRIMARY KEY(telegram_account_id, chat_id),
            FOREIGN KEY(telegram_account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_telegram_dialog_cache_account_position
            ON telegram_dialog_cache(telegram_account_id, position);
        """)
        _migrate_message_tags_chat_id(conn)
        _migrate_dialog_peer_metadata(conn)
        _set_schema_version(conn, SCHEMA_VERSION)
        conn.commit()
    finally:
        conn.close()


def _migrate_message_tags_chat_id(conn: sqlite3.Connection) -> None:
    """Upgrade the legacy message_tags key without discarding existing tags."""
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(message_tags)").fetchall()
    }
    if "chat_id" in columns:
        return

    conn.executescript(
        """
        ALTER TABLE message_tags RENAME TO message_tags_legacy;

        CREATE TABLE message_tags (
            telegram_account_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL DEFAULT 0,
            message_id INTEGER NOT NULL,
            tags TEXT,
            PRIMARY KEY(telegram_account_id, chat_id, message_id),
            FOREIGN KEY(telegram_account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
        );

        INSERT INTO message_tags(telegram_account_id, chat_id, message_id, tags)
        SELECT telegram_account_id, 0, message_id, tags
        FROM message_tags_legacy;

        DROP TABLE message_tags_legacy;
        """
    )



def _migrate_dialog_peer_metadata(conn: sqlite3.Connection) -> None:
    """Add persisted Pyrogram peer metadata to existing dialog caches."""
    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(telegram_dialog_cache)"
        ).fetchall()
    }

    if "peer_access_hash" not in columns:
        conn.execute(
            "ALTER TABLE telegram_dialog_cache "
            "ADD COLUMN peer_access_hash INTEGER"
        )

    if "peer_type" not in columns:
        conn.execute(
            "ALTER TABLE telegram_dialog_cache "
            "ADD COLUMN peer_type TEXT NOT NULL DEFAULT ''"
        )


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        """
        INSERT INTO schema_meta(key, value)
        VALUES('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        (str(version),),
    )


def get_schema_version(db_file: str) -> int:
    conn = get_db(db_file)
    try:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key='schema_version'"
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()
