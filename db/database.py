import sqlite3


def get_db(db_file: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_database(db_file: str) -> None:
    conn = get_db(db_file)
    try:
        conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS message_tags (
            telegram_account_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            tags TEXT,
            PRIMARY KEY(telegram_account_id, message_id),
            FOREIGN KEY(telegram_account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE
        );
        """)
        conn.commit()
    finally:
        conn.close()
