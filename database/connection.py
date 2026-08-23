import sqlite3
DB_FILE="telegram_manager.db"
def get_db():
 c=sqlite3.connect(DB_FILE,timeout=30); c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON"); return c
def initialize_database():
 c=get_db()
 try:
  c.executescript("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,password_salt TEXT NOT NULL,display_name TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS telegram_accounts (id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,telegram_user_id INTEGER NOT NULL,phone_number TEXT,username TEXT,first_name TEXT,last_name TEXT,encrypted_session BLOB NOT NULL,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,UNIQUE(user_id,telegram_user_id),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE); CREATE TABLE IF NOT EXISTS message_tags (telegram_account_id INTEGER NOT NULL,message_id INTEGER NOT NULL,tags TEXT,PRIMARY KEY(telegram_account_id,message_id),FOREIGN KEY(telegram_account_id) REFERENCES telegram_accounts(id) ON DELETE CASCADE);"""); c.commit()
 finally:c.close()
