from db.database import get_db


def get_tags(db_file: str, account_id: int, message_id: int) -> list[str]:
    conn = get_db(db_file)
    try:
        r = conn.execute("SELECT tags FROM message_tags WHERE telegram_account_id=? AND message_id=?", (account_id,message_id)).fetchone()
        return r[0].split(",") if r and r[0] else []
    finally: conn.close()


def save_tags(db_file: str, account_id: int, message_id: int, tags: list[str]) -> None:
    value = ",".join(t.strip() for t in tags if t.strip())
    conn = get_db(db_file)
    try:
        conn.execute("INSERT OR REPLACE INTO message_tags(telegram_account_id,message_id,tags) VALUES(?,?,?)", (account_id,message_id,value))
        conn.commit()
    finally: conn.close()


def all_tags(db_file: str, account_id: int) -> list[str]:
    conn = get_db(db_file)
    try:
        rows = conn.execute("SELECT tags FROM message_tags WHERE telegram_account_id=?", (account_id,)).fetchall()
        result=set()
        for r in rows:
            if r[0]: result.update(x.strip() for x in r[0].split(",") if x.strip())
        return sorted(result)
    finally: conn.close()
