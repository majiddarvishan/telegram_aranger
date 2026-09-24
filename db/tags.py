from db.database import get_db


def get_tags(
    db_file: str,
    account_id: int,
    chat_id: int,
    message_id: int,
) -> list[str]:
    conn = get_db(db_file)
    try:
        row = conn.execute(
            """
            SELECT tags
            FROM message_tags
            WHERE telegram_account_id=? AND chat_id=? AND message_id=?
            """,
            (account_id, chat_id, message_id),
        ).fetchone()
        return row[0].split(",") if row and row[0] else []
    finally:
        conn.close()


def save_tags(
    db_file: str,
    account_id: int,
    chat_id: int,
    message_id: int,
    tags: list[str],
) -> None:
    value = ",".join(tag.strip() for tag in tags if tag.strip())
    conn = get_db(db_file)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO message_tags(
                telegram_account_id, chat_id, message_id, tags
            ) VALUES(?,?,?,?)
            """,
            (account_id, chat_id, message_id, value),
        )
        conn.commit()
    finally:
        conn.close()


def all_tags(db_file: str, account_id: int) -> list[str]:
    conn = get_db(db_file)
    try:
        rows = conn.execute(
            "SELECT tags FROM message_tags WHERE telegram_account_id=? AND chat_id<>0",
            (account_id,),
        ).fetchall()
        result = set()
        for row in rows:
            if row[0]:
                result.update(
                    value.strip()
                    for value in row[0].split(",")
                    if value.strip()
                )
        return sorted(result)
    finally:
        conn.close()
