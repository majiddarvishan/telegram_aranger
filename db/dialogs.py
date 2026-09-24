from datetime import datetime, timezone

from db.database import get_db


def load_dialogs(db_file: str, account_id: int) -> list[dict]:
    conn = get_db(db_file)
    try:
        rows = conn.execute(
            """
            SELECT
                chat_id,
                title,
                chat_type,
                username,
                peer_access_hash,
                peer_type
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
            "peer_access_hash": row[4],
            "peer_type": row[5] or "",
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
                peer_access_hash,
                peer_type,
                fetched_at
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(telegram_account_id, chat_id)
            DO UPDATE SET
                position=excluded.position,
                title=excluded.title,
                chat_type=excluded.chat_type,
                username=excluded.username,
                peer_access_hash=excluded.peer_access_hash,
                peer_type=excluded.peer_type,
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
                    dialog.get("peer_access_hash"),
                    dialog.get("peer_type", ""),
                    fetched_at,
                )
                for position, dialog in enumerate(dialogs)
            ],
        )
        conn.commit()
    finally:
        conn.close()



def load_peer_records(
    db_file: str,
    account_id: int,
) -> list[tuple[int, int, str, str, str]]:
    """Return Pyrogram storage-compatible peer tuples for one account."""
    dialogs = load_dialogs(db_file, account_id)
    records = []

    for dialog in dialogs:
        peer_type = dialog.get("peer_type", "")
        if not peer_type:
            continue

        access_hash = dialog.get("peer_access_hash")
        records.append(
            (
                int(dialog["id"]),
                int(access_hash or 0),
                peer_type,
                dialog.get("username", ""),
                "",
            )
        )

    return records


def cache_has_peer_metadata(dialogs: list[dict]) -> bool:
    """True when every cached dialog came from the peer-aware schema."""
    return bool(dialogs) and all(
        bool(dialog.get("peer_type"))
        for dialog in dialogs
    )
