from database.connection import get_db
from services.auth_service import encrypt_session
# 8. Telegram Account Database
# =========================================================

def get_telegram_accounts(
    user_id: int,
) -> list[dict]:
    """Return all Telegram accounts belonging to a Web user."""

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT
                id,
                telegram_user_id,
                phone_number,
                username,
                first_name,
                last_name
            FROM telegram_accounts
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()

        return [
            {
                "id": row[0],
                "telegram_user_id": row[1],
                "phone_number": row[2],
                "username": row[3],
                "first_name": row[4],
                "last_name": row[5],
            }
            for row in rows
        ]

    finally:

        conn.close()


def get_telegram_account(
    user_id: int,
    account_id: int,
) -> dict | None:
    """Return one Telegram account."""

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT
                id,
                telegram_user_id,
                phone_number,
                username,
                first_name,
                last_name,
                encrypted_session
            FROM telegram_accounts
            WHERE id = ?
              AND user_id = ?
            """,
            (
                account_id,
                user_id,
            ),
        ).fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "telegram_user_id": row[1],
            "phone_number": row[2],
            "username": row[3],
            "first_name": row[4],
            "last_name": row[5],
            "encrypted_session": row[6],
        }

    finally:

        conn.close()


def save_telegram_account(
    user_id: int,
    telegram_user: dict,
    session_string: str,
) -> int:
    """Create or update a Telegram account."""

    encrypted_session = encrypt_session(
        session_string
    )

    conn = get_db()

    try:

        existing = conn.execute(
            """
            SELECT id
            FROM telegram_accounts
            WHERE user_id = ?
              AND telegram_user_id = ?
            """,
            (
                user_id,
                telegram_user["id"],
            ),
        ).fetchone()

        if existing:

            account_id = existing[0]

            conn.execute(
                """
                UPDATE telegram_accounts
                SET
                    phone_number = ?,
                    username = ?,
                    first_name = ?,
                    last_name = ?,
                    encrypted_session = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    telegram_user.get(
                        "phone_number"
                    ),
                    telegram_user.get(
                        "username"
                    ),
                    telegram_user.get(
                        "first_name"
                    ),
                    telegram_user.get(
                        "last_name"
                    ),
                    encrypted_session,
                    account_id,
                ),
            )

        else:

            cursor = conn.execute(
                """
                INSERT INTO telegram_accounts (
                    user_id,
                    telegram_user_id,
                    phone_number,
                    username,
                    first_name,
                    last_name,
                    encrypted_session
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    telegram_user["id"],
                    telegram_user.get(
                        "phone_number"
                    ),
                    telegram_user.get(
                        "username"
                    ),
                    telegram_user.get(
                        "first_name"
                    ),
                    telegram_user.get(
                        "last_name"
                    ),
                    encrypted_session,
                ),
            )

            account_id = cursor.lastrowid

        conn.commit()

        return account_id

    finally:

        conn.close()


def delete_telegram_account(
    user_id: int,
    account_id: int,
) -> None:
    """Delete a Telegram account and its tags."""

    conn = get_db()

    try:

        conn.execute(
            """
            DELETE FROM message_tags
            WHERE telegram_account_id = ?
            """,
            (account_id,),
        )

        conn.execute(
            """
            DELETE FROM telegram_accounts
            WHERE id = ?
              AND user_id = ?
            """,
            (
                account_id,
                user_id,
            ),
        )

        conn.commit()

    finally:

        conn.close()


