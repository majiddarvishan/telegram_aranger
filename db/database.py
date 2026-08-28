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
