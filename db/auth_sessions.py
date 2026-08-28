import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from db.database import get_db


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db_file: str, user_id: int, days: int) -> str:
    token = secrets.token_urlsafe(48)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    conn = get_db(db_file)
    try:
        conn.execute(
            "INSERT INTO web_sessions (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
            (user_id, token_hash, expires_at.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return token


def get_user_by_session(db_file: str, token: str) -> dict | None:
    if not token:
        return None

    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    conn = get_db(db_file)
    try:
        row = conn.execute(
            """
            SELECT u.id, u.username, u.display_name, s.expires_at
            FROM web_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()

        if not row:
            return None

        try:
            expires_at = datetime.fromisoformat(row[3])
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

        if expires_at <= now:
            conn.execute("DELETE FROM web_sessions WHERE token_hash = ?", (token_hash,))
            conn.commit()
            return None

        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2] or row[1],
        }
    finally:
        conn.close()


def delete_session(db_file: str, token: str) -> None:
    if not token:
        return
    conn = get_db(db_file)
    try:
        conn.execute(
            "DELETE FROM web_sessions WHERE token_hash = ?",
            (_hash_token(token),),
        )
        conn.commit()
    finally:
        conn.close()


def delete_user_sessions(db_file: str, user_id: int) -> None:
    conn = get_db(db_file)
    try:
        conn.execute("DELETE FROM web_sessions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
