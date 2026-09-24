from datetime import datetime, timedelta, timezone

from db.database import get_db


def normalize_username(username: str) -> str:
    return username.strip().lower()


def cleanup_login_attempts(db_file: str, window_minutes: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    conn = get_db(db_file)
    try:
        conn.execute(
            "DELETE FROM web_login_attempts WHERE attempted_at < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


def is_login_rate_limited(
    db_file: str,
    username: str,
    max_attempts: int,
    window_minutes: int,
) -> bool:
    normalized = normalize_username(username)
    if not normalized:
        return False

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    conn = get_db(db_file)
    try:
        conn.execute(
            "DELETE FROM web_login_attempts WHERE attempted_at < ?",
            (cutoff.isoformat(),),
        )
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM web_login_attempts
            WHERE username=? AND attempted_at>=?
            """,
            (normalized, cutoff.isoformat()),
        ).fetchone()[0]
        conn.commit()
        return count >= max_attempts
    finally:
        conn.close()


def record_failed_login(db_file: str, username: str) -> None:
    normalized = normalize_username(username)
    if not normalized:
        return

    conn = get_db(db_file)
    try:
        conn.execute(
            """
            INSERT INTO web_login_attempts(username, attempted_at)
            VALUES(?, ?)
            """,
            (normalized, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def clear_failed_logins(db_file: str, username: str) -> None:
    normalized = normalize_username(username)
    if not normalized:
        return

    conn = get_db(db_file)
    try:
        conn.execute(
            "DELETE FROM web_login_attempts WHERE username=?",
            (normalized,),
        )
        conn.commit()
    finally:
        conn.close()
