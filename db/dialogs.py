from datetime import datetime, timezone

from db.database import get_db


def load_dialogs(db_file: str, account_id: int) -> list[dict]:
    conn = get_db(db_file)
    try:
        rows = conn.execute(
            """
            SELECT chat_id, title, chat_type, username
            FROM telegram_dialog_cache
            WHERE telegram_account_id=?
              AND fetched_at=(
                  SELECT MAX(fetched_at)
                  FROM telegram_dialog_cache
                  WHERE telegram_account_id=?
              )
            ORDER BY position ASC
            """,
            (account_id, account_id),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row[0],
            "title": row[1],
            "type": row[2],
            "username": row[3] or "",
        }
        for row in rows
    ]


def replace_dialogs(
    db_file: str,
    account_id: int,
    dialogs: list[dict],
) -> None:
    if not dialogs:
        return

    fetched_at = datetime.now(timezone.utc).isoformat()
    conn = get_db(db_file)
    try:
        conn.executemany(
            """
            INSERT INTO telegram_dialog_cache(
                telegram_account_id,
                chat_id,
                position,
                title,
                chat_type,
                username,
                fetched_at
            )
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(telegram_account_id, chat_id)
            DO UPDATE SET
                position=excluded.position,
                title=excluded.title,
                chat_type=excluded.chat_type,
                username=excluded.username,
                fetched_at=excluded.fetched_at
            """,
            [
                (
                    account_id,
                    int(dialog["id"]),
                    position,
                    dialog["title"],
                    dialog["type"],
                    dialog.get("username", ""),
                    fetched_at,
                )
                for position, dialog in enumerate(dialogs)
            ],
        )
        conn.commit()
    finally:
        conn.close()
