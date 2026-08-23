import hashlib
import hmac
import secrets
import sqlite3
from cryptography.fernet import Fernet
from config.settings import SESSION_ENCRYPTION_KEY
from database.connection import get_db
# 3. Password Hashing
# =========================================================

PASSWORD_ITERATIONS = 310_000


def hash_password(
    password: str,
    salt: bytes | None = None,
) -> tuple[str, str]:
    """Hash a password using PBKDF2-HMAC-SHA256."""

    if salt is None:
        salt = secrets.token_bytes(32)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )

    return (
        salt.hex(),
        password_hash.hex(),
    )


def verify_password(
    password: str,
    salt_hex: str,
    expected_hash_hex: str,
) -> bool:
    """Verify a password against a stored hash."""

    salt = bytes.fromhex(
        salt_hex
    )

    _, password_hash = hash_password(
        password,
        salt,
    )

    return hmac.compare_digest(
        password_hash,
        expected_hash_hex,
    )


# =========================================================
# 4. Session Encryption
# =========================================================

def get_cipher() -> Fernet:
    """Create the Fernet encryption object."""

    return Fernet(
        SESSION_ENCRYPTION_KEY
    )


def encrypt_session(
    session_string: str,
) -> bytes:
    """Encrypt a Pyrogram session string."""

    return get_cipher().encrypt(
        session_string.encode()
    )


def decrypt_session(
    encrypted_session: bytes,
) -> str:
    """Decrypt a Pyrogram session string."""

    return get_cipher().decrypt(
        encrypted_session
    ).decode()


# =========================================================
# 5. Telegram Runtime
# =========================================================

class TelegramRuntime:
    """
    Owns one asyncio event loop and one Pyrogram Client.

    The event loop lives in a dedicated background thread.
    This prevents a Pyrogram Client from being moved between
    different asyncio event loops during Streamlit reruns.
    """

    def __init__(self):
        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
        )

        self.thread.start()

        self.client = None

    def _run_loop(self):
        """Run the background asyncio event loop."""

        asyncio.set_event_loop(
            self.loop
        )

        self.loop.run_forever()

    def run(
        self,
        coro,
    ):
        """Execute a coroutine on the Telegram event loop."""

        future: Future = (
            asyncio.run_coroutine_threadsafe(
                coro,
                self.loop,
            )
        )

        return future.result()

    def stop(self):
        """Stop the runtime."""

        if self.loop.is_running():

            self.loop.call_soon_threadsafe(
                self.loop.stop
            )

        self.thread.join(
            timeout=2
        )


def get_runtime() -> TelegramRuntime:
    """Get the Telegram runtime for the current Web session."""

    runtime = st.session_state.get(
        "telegram_runtime"
    )

    if runtime is None:

        runtime = TelegramRuntime()

        st.session_state.telegram_runtime = (
            runtime
        )

    return runtime


# 7. Web User Database
# =========================================================

def create_user(
    username: str,
    password: str,
    display_name: str,
) -> bool:
    """Create a new Web user."""

    username = username.strip().lower()

    salt, password_hash = hash_password(
        password
    )

    conn = get_db()

    try:

        conn.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                password_salt,
                display_name
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                salt,
                display_name.strip(),
            ),
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def authenticate_user(
    username: str,
    password: str,
) -> dict | None:
    """Authenticate a Web user."""

    conn = get_db()

    try:

        row = conn.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                password_salt,
                display_name
            FROM users
            WHERE username = ?
            """,
            (
                username.strip().lower(),
            ),
        ).fetchone()

        if not row:
            return None

        if not verify_password(
            password,
            row[3],
            row[2],
        ):
            return None

        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[4] or row[1],
        }

    finally:

        conn.close()


# =========================================================
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


