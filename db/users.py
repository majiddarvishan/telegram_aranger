import hashlib
import hmac
import secrets
import sqlite3
from db.database import get_db

PASSWORD_ITERATIONS = 310_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hash: str) -> bool:
    _, digest = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest, expected_hash)


def create_user(db_file: str, username: str, password: str, display_name: str) -> bool:
    salt, digest = hash_password(password)
    conn = get_db(db_file)
    try:
        conn.execute("INSERT INTO users(username,password_hash,password_salt,display_name) VALUES(?,?,?,?)",
                     (username.strip().lower(), digest, salt, display_name.strip()))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def authenticate_user(db_file: str, username: str, password: str) -> dict | None:
    conn = get_db(db_file)
    try:
        row = conn.execute("SELECT id,username,password_hash,password_salt,display_name FROM users WHERE username=?",
                           (username.strip().lower(),)).fetchone()
        if not row or not verify_password(password, row[3], row[2]):
            return None
        return {"id": row[0], "username": row[1], "display_name": row[4] or row[1]}
    finally:
        conn.close()
