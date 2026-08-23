from database.connection import get_db
# 19. Tags
# =========================================================

def get_tags(
    account_id: int,
    message_id: int,
) -> list[str]:
    """Return tags for a message."""

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT tags
            FROM message_tags
            WHERE telegram_account_id = ?
              AND message_id = ?
            """,
            (
                account_id,
                message_id,
            ),
        ).fetchone()

        if not row or not row[0]:
            return []

        return row[0].split(",")

    finally:

        conn.close()


def save_tags(
    account_id: int,
    message_id: int,
    tags: list[str],
):
    """Save tags for a message."""

    tags_string = ",".join(
        tag.strip()
        for tag in tags
        if tag.strip()
    )

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT OR REPLACE INTO message_tags (
                telegram_account_id,
                message_id,
                tags
            )
            VALUES (?, ?, ?)
            """,
            (
                account_id,
                message_id,
                tags_string,
            ),
        )

        conn.commit()

    finally:

        conn.close()


def get_all_tags(
    account_id: int,
) -> list[str]:
    """Return all tags belonging to an account."""

    conn = get_db()

    try:

        rows = conn.execute(
            """
            SELECT tags
            FROM message_tags
            WHERE telegram_account_id = ?
            """,
            (account_id,),
        ).fetchall()

        tags = set()

        for row in rows:

            if row[0]:

                tags.update(
                    row[0].split(",")
                )

        return sorted(tags)

    finally:

        conn.close()


