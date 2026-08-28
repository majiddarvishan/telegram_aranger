from db.database import get_db


def list_accounts(db_file: str, user_id: int) -> list[dict]:
    conn = get_db(db_file)
    try:
        rows = conn.execute("""SELECT id,telegram_user_id,phone_number,username,first_name,last_name
                              FROM telegram_accounts WHERE user_id=? ORDER BY id""", (user_id,)).fetchall()
        return [dict(id=r[0], telegram_user_id=r[1], phone_number=r[2], username=r[3], first_name=r[4], last_name=r[5]) for r in rows]
    finally:
        conn.close()


def get_account(db_file: str, user_id: int, account_id: int) -> dict | None:
    conn = get_db(db_file)
    try:
        r = conn.execute("""SELECT id,telegram_user_id,phone_number,username,first_name,last_name,encrypted_session
                           FROM telegram_accounts WHERE id=? AND user_id=?""", (account_id,user_id)).fetchone()
        if not r: return None
        return dict(id=r[0], telegram_user_id=r[1], phone_number=r[2], username=r[3], first_name=r[4], last_name=r[5], encrypted_session=r[6])
    finally:
        conn.close()


def save_account(db_file: str, user_id: int, telegram_user: dict, encrypted_session: bytes) -> int:
    conn = get_db(db_file)
    try:
        existing = conn.execute("SELECT id FROM telegram_accounts WHERE user_id=? AND telegram_user_id=?",
                                (user_id, telegram_user["id"])).fetchone()
        data = (telegram_user.get("phone_number",""), telegram_user.get("username",""),
                telegram_user.get("first_name",""), telegram_user.get("last_name",""), encrypted_session)
        if existing:
            conn.execute("""UPDATE telegram_accounts SET phone_number=?,username=?,first_name=?,last_name=?,encrypted_session=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", data + (existing[0],))
            account_id = existing[0]
        else:
            cur = conn.execute("""INSERT INTO telegram_accounts(user_id,telegram_user_id,phone_number,username,first_name,last_name,encrypted_session)
                                 VALUES(?,?,?,?,?,?,?)""", (user_id, telegram_user["id"], *data))
            account_id = cur.lastrowid
        conn.commit()
        return int(account_id)
    finally:
        conn.close()


def delete_account(db_file: str, user_id: int, account_id: int) -> None:
    conn = get_db(db_file)
    try:
        conn.execute("DELETE FROM message_tags WHERE telegram_account_id=?", (account_id,))
        conn.execute("DELETE FROM telegram_accounts WHERE id=? AND user_id=?", (account_id,user_id))
        conn.commit()
    finally:
        conn.close()
