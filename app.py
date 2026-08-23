import asyncio
import os
import sqlite3
import hashlib
import hmac
import secrets
import threading
from datetime import date
from concurrent.futures import Future

from dotenv import load_dotenv
from cryptography.fernet import Fernet

# ---------------------------------------------------------
# Python 3.14 / Pyrogram compatibility
# ---------------------------------------------------------
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import streamlit as st

from pyrogram import Client
from pyrogram.errors import (
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    PasswordHashInvalid,
    SessionPasswordNeeded,
)
# =========================================================
# 1. Environment
# =========================================================

load_dotenv()


def get_config(name: str) -> str:
    """Read a required configuration value."""

    value = os.getenv(name)

    if not value:
        try:
            value = st.secrets[name]
        except Exception:
            value = None

    if not value:
        raise RuntimeError(
            f"Required configuration '{name}' is not set."
        )

    return value


API_ID = int(
    get_config("TELEGRAM_API_ID")
)

API_HASH = get_config(
    "TELEGRAM_API_HASH"
)

SESSION_ENCRYPTION_KEY = get_config(
    "TELEGRAM_SESSION_ENCRYPTION_KEY"
).strip().encode()

try:
    Fernet(SESSION_ENCRYPTION_KEY)
except Exception as exc:
    raise RuntimeError(
        "TELEGRAM_SESSION_ENCRYPTION_KEY is invalid. "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    ) from exc


# =========================================================
# 2. Database
# =========================================================

DB_FILE = "telegram_manager.db"


def get_db() -> sqlite3.Connection:
    """Create a database connection."""

    conn = sqlite3.connect(
        DB_FILE,
        timeout=30,
    )

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

    conn.execute(
        "PRAGMA foreign_keys=ON"
    )

    return conn


def initialize_database() -> None:
    """Initialize application database."""

    conn = get_db()

    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telegram_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                telegram_user_id INTEGER NOT NULL,
                phone_number TEXT,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                encrypted_session BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                UNIQUE (
                    user_id,
                    telegram_user_id
                ),

                FOREIGN KEY (
                    user_id
                )
                REFERENCES users(id)
                ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_tags (
                telegram_account_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                tags TEXT,

                PRIMARY KEY (
                    telegram_account_id,
                    message_id
                ),

                FOREIGN KEY (
                    telegram_account_id
                )
                REFERENCES telegram_accounts(id)
                ON DELETE CASCADE
            )
            """
        )

        conn.commit()

    finally:
        conn.close()


initialize_database()


# =========================================================
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


# =========================================================
# 6. Proxy
# =========================================================

def get_proxy_config() -> dict | None:
    """Build the SOCKS5 proxy configuration."""

    if not st.session_state.get(
        "use_proxy",
        True,
    ):
        return None

    proxy = {
        "scheme": "socks5",
        "hostname": st.session_state.get(
            "proxy_host",
            "127.0.0.1",
        ),
        "port": int(
            st.session_state.get(
                "proxy_port",
                1080,
            )
        ),
    }

    username = st.session_state.get(
        "proxy_user",
        "",
    ).strip()

    password = st.session_state.get(
        "proxy_pass",
        "",
    ).strip()

    if username:
        proxy["username"] = username

    if password:
        proxy["password"] = password

    return proxy


# =========================================================
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


# =========================================================
# 9. Telegram Client Creation
# =========================================================

async def create_client(
    session_string: str | None = None,
    proxy: dict | None = None,
) -> Client:
    """Create a Pyrogram client."""

    kwargs = {
        "name": "telegram",
        "api_id": API_ID,
        "api_hash": API_HASH,
        "proxy": proxy,
        "in_memory": True,
    }

    if session_string:
        kwargs["session_string"] = session_string

    client = Client(
        **kwargs
    )

    await client.connect()

    return client


def set_runtime_client(
    client: Client,
) -> None:
    """Store the active client in the runtime."""

    runtime = get_runtime()

    runtime.client = client


def get_runtime_client() -> Client:
    """Return the current Pyrogram client."""

    runtime = get_runtime()

    if runtime.client is None:
        raise RuntimeError(
            "Telegram client is not initialized."
        )

    return runtime.client


# =========================================================
# 10. Telegram Helpers
# =========================================================

def user_to_dict(
    user,
) -> dict:
    """Convert a Pyrogram User to a dictionary."""

    return {
        "id": user.id,
        "phone_number": user.phone_number or "",
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
    }


# =========================================================
# 11. Restore Telegram Account
# =========================================================

async def restore_telegram_account_async(
    account: dict,
    proxy: dict | None,
) -> dict:
    """Restore an encrypted Telegram session."""

    session_string = decrypt_session(
        account["encrypted_session"]
    )

    client = await create_client(
        session_string=session_string,
        proxy=proxy,
    )

    try:

        me = await client.get_me()

        set_runtime_client(
            client
        )

        return user_to_dict(
            me
        )

    except Exception:

        try:
            await client.disconnect()
        except Exception:
            pass

        raise


def restore_telegram_account(
    account: dict,
    proxy: dict | None,
) -> dict:
    """Restore a Telegram account."""

    runtime = get_runtime()

    return runtime.run(
        restore_telegram_account_async(
            account,
            proxy,
        )
    )


# =========================================================
# 12. Telegram Login - Send Code
# =========================================================

async def send_login_code_async(
    phone_number: str,
    proxy: dict | None,
):
    """Send Telegram authentication code."""

    runtime = get_runtime()

    if runtime.client is not None:

        try:
            await runtime.client.disconnect()
        except Exception:
            pass

        runtime.client = None

    client = await create_client(
        proxy=proxy,
    )

    sent_code = await client.send_code(
        phone_number
    )

    set_runtime_client(
        client
    )

    return sent_code.phone_code_hash


def send_login_code(
    phone_number: str,
    proxy: dict | None,
):
    """Send Telegram authentication code."""

    return get_runtime().run(
        send_login_code_async(
            phone_number,
            proxy,
        )
    )


# =========================================================
# 13. Telegram Login - Verify Code
# =========================================================

async def verify_login_code_async(
    phone_number: str,
    phone_code_hash: str,
    phone_code: str,
):
    """Verify Telegram login code."""

    client = get_runtime_client()

    try:

        await client.sign_in(
            phone_number=phone_number,
            phone_code_hash=phone_code_hash,
            phone_code=phone_code,
        )

    except SessionPasswordNeeded:

        return "2fa", None

    me = await client.get_me()

    return (
        "success",
        user_to_dict(me),
    )


def verify_login_code(
    phone_number: str,
    phone_code_hash: str,
    phone_code: str,
):
    """Verify Telegram login code."""

    return get_runtime().run(
        verify_login_code_async(
            phone_number,
            phone_code_hash,
            phone_code,
        )
    )


# =========================================================
# 14. Telegram 2FA
# =========================================================

async def verify_2fa_async(
    password: str,
):
    """Verify Telegram two-step verification password."""

    client = get_runtime_client()

    me = await client.check_password(
        password
    )

    return user_to_dict(
        me
    )


def verify_2fa(
    password: str,
):
    """Verify Telegram 2FA password."""

    return get_runtime().run(
        verify_2fa_async(
            password
        )
    )


# =========================================================
# 15. Export Telegram Session
# =========================================================

async def export_current_session_async():
    """Export the authorized Pyrogram session."""

    client = get_runtime_client()

    return await client.export_session_string()


def export_current_session() -> str:
    """Export the authorized Pyrogram session."""

    return get_runtime().run(
        export_current_session_async()
    )


# =========================================================
# 16. Disconnect Telegram
# =========================================================

async def disconnect_telegram_async():
    """Disconnect the active Telegram client without logging out."""

    runtime = get_runtime()
    client = runtime.client

    if client is None:
        return

    try:
        if client.is_connected:
            await client.disconnect()
    finally:
        runtime.client = None


def disconnect_telegram():
    """Disconnect the active Telegram client without invalidating the saved session."""

    get_runtime().run(
        disconnect_telegram_async()
    )


async def logout_telegram_async():
    """Log out the active Telegram account from Telegram."""

    runtime = get_runtime()
    client = runtime.client

    if client is None:
        return

    try:
        await client.log_out()
    finally:
        runtime.client = None


def logout_telegram():
    """Log out the active Telegram account from Telegram."""

    get_runtime().run(
        logout_telegram_async()
    )


# =========================================================
# 17. Fetch Saved Messages
# =========================================================

async def fetch_saved_messages_async(
    limit: int = 100,
) -> list[dict]:
    """Fetch recent Saved Messages."""

    client = get_runtime_client()

    me = await client.get_me()

    messages = []

    async for message in client.get_chat_history(
        "me",
        limit=limit,
    ):

        content = (
            message.text
            or message.caption
            or "[Media / File]"
        )

        messages.append(
            {
                "id": message.id,
                "text": content,
                "date": str(message.date),
                "user_id": me.id,
            }
        )

    return messages


def fetch_saved_messages(
    limit: int = 100,
) -> list[dict]:
    """Fetch recent Saved Messages."""

    return get_runtime().run(
        fetch_saved_messages_async(
            limit
        )
    )


# =========================================================
# 18.1 Fetch Saved Messages for a Selected Date
# =========================================================

async def fetch_saved_messages_for_date_async(
    selected_date: date,
) -> list[dict]:
    """Fetch Saved Messages belonging to the selected calendar date."""

    client = get_runtime_client()
    me = await client.get_me()
    messages = []

    async for message in client.get_chat_history("me"):
        if message.date is None:
            continue

        message_date = message.date.date()

        if message_date < selected_date:
            break

        if message_date != selected_date:
            continue

        content = (
            message.text
            or message.caption
            or "[Media / File]"
        )

        messages.append({
            "id": message.id,
            "text": content,
            "date": str(message.date),
            "user_id": me.id,
        })

    return messages


def fetch_saved_messages_for_date(
    selected_date: date,
) -> list[dict]:
    """Fetch Saved Messages for a selected calendar date."""

    return get_runtime().run(
        fetch_saved_messages_for_date_async(
            selected_date
        )
    )


# =========================================================
# 18. Delete Telegram Message
# =========================================================

async def delete_message_async(
    message_id: int,
):
    """Delete a Telegram message."""

    client = get_runtime_client()

    await client.delete_messages(
        "me",
        message_id,
    )


def delete_message(
    message_id: int,
):
    """Delete a Telegram message."""

    get_runtime().run(
        delete_message_async(
            message_id
        )
    )


# =========================================================
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


# =========================================================
# 20. Streamlit State
# =========================================================

def initialize_state():

    defaults = {
        "web_user": None,

        "telegram_runtime": None,

        "telegram_login_stage": "phone",

        "telegram_login_active": False,

        "telegram_login_phone": "",

        "telegram_phone_code_hash": "",

        "telegram_user": None,

        "selected_telegram_account_id": None,

        "messages": [],
        "selected_message_date": date.today(),
        "message_date_loaded": None,

        "use_proxy": True,

        "proxy_host": "127.0.0.1",

        "proxy_port": 1080,

        "proxy_user": "",

        "proxy_pass": "",
    }

    for key, value in defaults.items():

        if key not in st.session_state:

            st.session_state[key] = value


initialize_state()


# =========================================================
# 21. Page Configuration
# =========================================================

st.set_page_config(
    page_title="Telegram Saved Messages Manager",
    layout="wide",
)


# =========================================================
# 22. Authentication UI
# =========================================================

def reset_telegram_login_state() -> None:
    """Reset the Telegram login flow and disconnect its temporary client."""

    runtime = get_runtime()

    if runtime.client is not None:
        try:
            runtime.run(runtime.client.disconnect())
        except Exception:
            pass
        runtime.client = None

    st.session_state.telegram_login_stage = "phone"
    st.session_state.telegram_login_active = False
    st.session_state.telegram_login_phone = ""
    st.session_state.telegram_phone_code_hash = ""


def start_telegram_login() -> None:
    """Start a new Telegram account login flow."""

    reset_telegram_login_state()
    st.session_state.telegram_login_active = True
    st.session_state.telegram_user = None
    st.session_state.messages = []


def render_authentication():

    st.title(
        "🔐 Telegram Saved Messages Manager"
    )

    st.info(
        "Please login to the Web Application."
    )

    login_tab, register_tab = st.tabs(
        [
            "Login",
            "Create Account",
        ]
    )

    with login_tab:

        with st.form(
            "web_login_form"
        ):

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            login = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

        if login:

            user = authenticate_user(
                username,
                password,
            )

            if user:

                st.session_state.web_user = (
                    user
                )

                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )

    with register_tab:

        with st.form(
            "web_register_form"
        ):

            display_name = st.text_input(
                "Display Name"
            )

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
            )

            register = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if register:

            if not username.strip():

                st.error(
                    "Username is required."
                )

            elif len(password) < 8:

                st.error(
                    "Password must contain at least 8 characters."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            else:

                created = create_user(
                    username,
                    password,
                    display_name,
                )

                if created:

                    st.success(
                        "Account created. "
                        "You can now login."
                    )

                else:

                    st.error(
                        "Username already exists."
                    )


if st.session_state.web_user is None:

    render_authentication()

    st.stop()


# =========================================================
# 23. Sidebar - Web User
# =========================================================

web_user = st.session_state.web_user

st.sidebar.title(
    "👤 Account"
)

st.sidebar.write(
    f"**{web_user['display_name']}**"
)

st.sidebar.caption(
    f"@{web_user['username']}"
)


if st.sidebar.button(
    "🚪 Logout Web Application",
    use_container_width=True,
):

    runtime = st.session_state.get(
        "telegram_runtime"
    )

    if runtime:

        try:

            runtime.stop()

        except Exception:
            pass

    st.session_state.clear()

    st.rerun()


st.sidebar.markdown("---")


# =========================================================
# 24. Sidebar - Proxy
# =========================================================

st.sidebar.header(
    "⚙️ Network Settings"
)

st.session_state.use_proxy = (
    st.sidebar.checkbox(
        "Enable SOCKS5 Proxy",
        value=st.session_state.use_proxy,
    )
)

if st.session_state.use_proxy:

    st.session_state.proxy_host = (
        st.sidebar.text_input(
            "Proxy Host/IP",
            value=st.session_state.proxy_host,
        )
    )

    st.session_state.proxy_port = (
        st.sidebar.number_input(
            "Proxy Port",
            value=st.session_state.proxy_port,
            min_value=1,
            max_value=65535,
        )
    )

    st.session_state.proxy_user = (
        st.sidebar.text_input(
            "Username (Optional)",
            value=st.session_state.proxy_user,
        )
    )

    st.session_state.proxy_pass = (
        st.sidebar.text_input(
            "Password (Optional)",
            type="password",
            value=st.session_state.proxy_pass,
        )
    )


proxy_config = get_proxy_config()


# =========================================================
# 25. Telegram Accounts
# =========================================================

st.sidebar.markdown("---")

st.sidebar.header(
    "📱 Telegram Accounts"
)

telegram_accounts = get_telegram_accounts(
    web_user["id"]
)


# =========================================================
# 26. Add Telegram Account
# =========================================================

if st.sidebar.button(
    "➕ Add Telegram Account",
    use_container_width=True,
):
    start_telegram_login()
    st.rerun()


# =========================================================
# 27. Account Selector
# =========================================================

if telegram_accounts:

    account_options = {}

    for account in telegram_accounts:

        username = account["username"]

        if username:

            label = (
                f"@{username} "
                f"({account['telegram_user_id']})"
            )

        else:

            name = (
                f"{account['first_name']} "
                f"{account['last_name']}"
            ).strip()

            label = (
                f"{name or account['telegram_user_id']}"
            )

        account_options[
            account["id"]
        ] = label

    current_account_id = (
        st.session_state.selected_telegram_account_id
    )

    if (
        current_account_id
        not in account_options
    ):

        current_account_id = (
            next(
                iter(account_options)
            )
        )

        st.session_state.selected_telegram_account_id = (
            current_account_id
        )

    selected_account_id = (
        st.sidebar.selectbox(
            "Active Telegram Account",
            options=list(
                account_options.keys()
            ),
            index=list(
                account_options.keys()
            ).index(
                current_account_id
            ),
            format_func=lambda x:
                account_options[x],
        )
    )

    if (
        selected_account_id
        != st.session_state.selected_telegram_account_id
    ):

        st.session_state.selected_telegram_account_id = (
            selected_account_id
        )

        st.session_state.messages = []

        runtime = get_runtime()

        if runtime.client:

            try:
                runtime.run(
                    runtime.client.disconnect()
                )
            except Exception:
                pass

            runtime.client = None

        st.rerun()


# =========================================================
# 27. Connect Selected Telegram Account
# =========================================================

selected_account_id = (
    st.session_state.selected_telegram_account_id
)

if selected_account_id:

    selected_account = get_telegram_account(
        web_user["id"],
        selected_account_id,
    )

    runtime = get_runtime()

    if (
        selected_account
        and runtime.client is None
        and not st.session_state.telegram_login_active
    ):

        try:

            with st.spinner(
                "Connecting to Telegram..."
            ):

                telegram_user = (
                    restore_telegram_account(
                        selected_account,
                        proxy_config,
                    )
                )

            st.session_state.telegram_user = (
                telegram_user
            )

        except Exception as e:

            st.error(
                f"Failed to restore Telegram session: {e}"
            )

            st.session_state.telegram_user = None


# =========================================================
# 29. Connected Telegram Account
# =========================================================

if st.session_state.telegram_user:

    telegram_user = (
        st.session_state.telegram_user
    )

    st.sidebar.success(
        "🟢 Telegram Connected"
    )

    name = (
        f"{telegram_user['first_name']} "
        f"{telegram_user['last_name']}"
    ).strip()

    if name:

        st.sidebar.caption(
            f"👤 {name}"
        )

    if telegram_user["username"]:

        st.sidebar.caption(
            f"@{telegram_user['username']}"
        )

    st.sidebar.caption(
        f"ID: {telegram_user['id']}"
    )

    if st.sidebar.button(
        "🔌 Disconnect Telegram",
        use_container_width=True,
    ):
        try:
            with st.spinner("Disconnecting Telegram..."):
                disconnect_telegram()

            st.session_state.telegram_user = None
            st.session_state.messages = []
            st.rerun()

        except Exception as e:
            st.sidebar.error(
                f"Failed to disconnect Telegram: {e}"
            )

    if st.sidebar.button(
        "🚪 Logout Telegram Account",
        use_container_width=True,
    ):
        try:
            with st.spinner("Logging out from Telegram..."):
                logout_telegram()

            delete_telegram_account(
                web_user["id"],
                selected_account_id,
            )

            st.session_state.telegram_user = None
            st.session_state.selected_telegram_account_id = None
            st.session_state.messages = []
            st.rerun()

        except Exception as e:
            st.sidebar.error(
                f"Failed to logout Telegram: {e}"
            )

# =========================================================
# 30. Telegram Login UI
# =========================================================

if (
    not st.session_state.telegram_user
    and st.session_state.telegram_login_active
):

    st.sidebar.markdown("---")

    st.sidebar.header(
        "🔐 Add Telegram Account"
    )

    stage = (
        st.session_state.telegram_login_stage
    )

    # -----------------------------------------------------
    # Phone
    # -----------------------------------------------------

    if stage == "phone":

        with st.sidebar.form(
            "telegram_phone_form"
        ):

            phone = st.text_input(
                "Phone Number",
                placeholder="+989123456789",
            )

            send_code = st.form_submit_button(
                "📱 Send Login Code",
                use_container_width=True,
            )

        if send_code:

            phone = phone.strip()

            if not phone:

                st.sidebar.error(
                    "Phone number is required."
                )

            else:

                try:

                    with st.spinner(
                        "Sending Telegram code..."
                    ):

                        phone_code_hash = (
                            send_login_code(
                                phone,
                                proxy_config,
                            )
                        )

                    st.session_state.telegram_login_phone = (
                        phone
                    )

                    st.session_state.telegram_phone_code_hash = (
                        phone_code_hash
                    )

                    st.session_state.telegram_login_active = True
                    st.session_state.telegram_login_stage = "code"

                    st.rerun()

                except Exception as e:

                    st.sidebar.error(
                        f"Failed to send code: {e}"
                    )

    # -----------------------------------------------------
    # Code
    # -----------------------------------------------------

    elif stage == "code":

        st.sidebar.info(
            f"Code sent to "
            f"{st.session_state.telegram_login_phone}"
        )

        with st.sidebar.form(
            "telegram_code_form"
        ):

            code = st.text_input(
                "Telegram Code",
                placeholder="12345",
            )

            verify = st.form_submit_button(
                "✅ Verify Code",
                use_container_width=True,
            )

        if verify:

            code = code.strip()

            if not code:

                st.sidebar.error(
                    "Enter the Telegram code."
                )

            else:

                try:

                    status, telegram_user = (
                        verify_login_code(
                            st.session_state.telegram_login_phone,
                            st.session_state.telegram_phone_code_hash,
                            code,
                        )
                    )

                    if status == "2fa":

                        st.session_state.telegram_login_stage = (
                            "2fa"
                        )

                        st.rerun()

                    else:

                        session_string = (
                            export_current_session()
                        )

                        account_id = (
                            save_telegram_account(
                                web_user["id"],
                                telegram_user,
                                session_string,
                            )
                        )

                        st.session_state.telegram_user = (
                            telegram_user
                        )

                        st.session_state.selected_telegram_account_id = (
                            account_id
                        )

                        st.session_state.telegram_login_stage = "phone"
                        st.session_state.telegram_login_active = False

                        st.session_state.telegram_login_phone = (
                            ""
                        )

                        st.session_state.telegram_phone_code_hash = (
                            ""
                        )

                        st.session_state.messages = []

                        st.rerun()

                except PhoneCodeExpired:

                    st.sidebar.error(
                        "The Telegram code has expired. "
                        "Please request a new code."
                    )

                except PhoneCodeInvalid:

                    st.sidebar.error(
                        "The Telegram code is invalid."
                    )

                except PhoneNumberInvalid:

                    st.sidebar.error(
                        "The Telegram phone number is invalid."
                    )

                except Exception as e:

                    st.sidebar.error(
                        f"Code verification failed: {e}"
                    )

        if st.sidebar.button(
            "🔄 Resend Code",
            use_container_width=True,
        ):

            try:

                with st.spinner(
                    "Sending a new code..."
                ):

                    phone_code_hash = (
                        send_login_code(
                            st.session_state.telegram_login_phone,
                            proxy_config,
                        )
                    )

                st.session_state.telegram_phone_code_hash = (
                    phone_code_hash
                )

                st.sidebar.success(
                    "A new Telegram code was sent."
                )

                st.rerun()

            except Exception as e:

                st.sidebar.error(
                    f"Failed to resend code: {e}"
                )

        if st.sidebar.button(
            "↩️ Change Phone Number",
            use_container_width=True,
        ):

            runtime = get_runtime()

            if runtime.client:

                try:

                    runtime.run(
                        runtime.client.disconnect()
                    )

                except Exception:
                    pass

                runtime.client = None

            st.session_state.telegram_login_stage = (
                "phone"
            )

            st.session_state.telegram_login_phone = (
                ""
            )

            st.session_state.telegram_phone_code_hash = (
                ""
            )

            st.rerun()

    # -----------------------------------------------------
    # 2FA
    # -----------------------------------------------------

    elif stage == "2fa":

        st.sidebar.info(
            "This Telegram account has "
            "Two-Step Verification enabled."
        )

        with st.sidebar.form(
            "telegram_2fa_form"
        ):

            password = st.text_input(
                "Telegram 2FA Password",
                type="password",
            )

            login_2fa = st.form_submit_button(
                "🔓 Login",
                use_container_width=True,
            )

        if login_2fa:

            if not password:

                st.sidebar.error(
                    "Enter your Telegram 2FA password."
                )

            else:

                try:

                    telegram_user = (
                        verify_2fa(
                            password
                        )
                    )

                    session_string = (
                        export_current_session()
                    )

                    account_id = (
                        save_telegram_account(
                            web_user["id"],
                            telegram_user,
                            session_string,
                        )
                    )

                    st.session_state.telegram_user = (
                        telegram_user
                    )

                    st.session_state.selected_telegram_account_id = (
                        account_id
                    )

                    st.session_state.telegram_login_stage = "phone"
                    st.session_state.telegram_login_active = False

                    st.session_state.telegram_login_phone = (
                        ""
                    )

                    st.session_state.telegram_phone_code_hash = (
                        ""
                    )

                    st.session_state.messages = []

                    st.rerun()

                except PasswordHashInvalid:

                    st.sidebar.error(
                        "The Telegram 2FA password is incorrect."
                    )

                except Exception as e:

                    st.sidebar.error(
                        f"2FA verification failed: {e}"
                    )

        if st.sidebar.button(
            "↩️ Start Over",
            use_container_width=True,
        ):

            runtime = get_runtime()

            if runtime.client:

                try:

                    runtime.run(
                        runtime.client.disconnect()
                    )

                except Exception:
                    pass

                runtime.client = None

            st.session_state.telegram_login_stage = (
                "phone"
            )

            st.session_state.telegram_login_phone = (
                ""
            )

            st.session_state.telegram_phone_code_hash = (
                ""
            )

            st.rerun()


# =========================================================
# 30. Stop if Telegram is Not Connected
# =========================================================

if (
    not st.session_state.telegram_user
    or not st.session_state.selected_telegram_account_id
):

    st.info(
        "📱 Add or select a Telegram account "
        "from the sidebar."
    )

    st.stop()


# =========================================================
# 31. Active Account
# =========================================================

account_id = (
    st.session_state.selected_telegram_account_id
)


# =========================================================
# 32. Message Date Filter
# =========================================================

st.sidebar.markdown("---")
st.sidebar.header("📅 Message Date")

selected_message_date = st.sidebar.date_input(
    "Select date",
    value=st.session_state.selected_message_date,
    key="message_date_picker",
)

if selected_message_date != st.session_state.selected_message_date:
    st.session_state.selected_message_date = selected_message_date
    st.session_state.messages = []
    st.session_state.message_date_loaded = None

col_date_info, col_date_action = st.columns([3, 1])

with col_date_info:
    st.subheader(
        f"Messages for {selected_message_date.strftime('%Y-%m-%d')}"
    )

with col_date_action:
    refresh_date = st.button(
        "🔄 Refresh Selected Date",
        use_container_width=True,
    )

# =========================================================
# 33. Fetch Messages for Selected Date
# =========================================================

if (
    not st.session_state.messages
    or st.session_state.message_date_loaded != selected_message_date
    or refresh_date
):

    with st.spinner(
        f"Fetching messages for {selected_message_date}..."
    ):

        try:
            st.session_state.messages = (
                fetch_saved_messages_for_date(
                    selected_message_date
                )
            )
            st.session_state.message_date_loaded = selected_message_date

        except Exception as e:

            st.error(
                f"Failed to fetch messages: {e}"
            )

            st.session_state.messages = []
            st.session_state.message_date_loaded = selected_message_date

if not st.session_state.messages:
    st.info(
        f"No Saved Messages found for {selected_message_date.strftime('%Y-%m-%d')}."
    )


# =========================================================
# 34. Tags Filter
# =========================================================

all_tags = get_all_tags(
    account_id
)

selected_tag = st.sidebar.selectbox(
    "Filter by Tag:",
    ["All"] + all_tags,
)


# =========================================================
# 35. Search
# =========================================================

search_query = st.text_input(
    "🔍 Search message text:"
)


# =========================================================
# 36. Render Messages
# =========================================================

for message in st.session_state.messages:

    message_id = message["id"]

    text = message["text"]

    current_tags = get_tags(
        account_id,
        message_id,
    )

    if (
        selected_tag != "All"
        and selected_tag not in current_tags
    ):
        continue

    if (
        search_query
        and search_query.lower()
        not in text.lower()
    ):
        continue

    with st.container():

        st.markdown("---")

        col_content, col_actions = (
            st.columns([3, 1])
        )

        # -------------------------------------------------
        # Content
        # -------------------------------------------------

        with col_content:

            st.write(text)

            st.caption(
                f"📅 {message['date']} | "
                f"ID: {message_id}"
            )

            tg_link = (
                f"https://t.me/c/"
                f"{message['user_id']}/"
                f"{message_id}"
            )

            st.markdown(
                "[🔗 Open in Telegram]"
                f"({tg_link})"
            )

        # -------------------------------------------------
        # Actions
        # -------------------------------------------------

        with col_actions:

            tags_input = st.text_input(
                "Tags (comma separated):",
                value=", ".join(
                    current_tags
                ),
                key=(
                    f"tags_"
                    f"{account_id}_"
                    f"{message_id}"
                ),
            )

            if st.button(
                "Save Tags",
                key=(
                    f"save_"
                    f"{account_id}_"
                    f"{message_id}"
                ),
            ):

                save_tags(
                    account_id,
                    message_id,
                    tags_input.split(","),
                )

                st.success(
                    "Tags updated."
                )

                st.rerun()

            if st.button(
                "🗑️ Delete Message",
                key=(
                    f"delete_"
                    f"{account_id}_"
                    f"{message_id}"
                ),
                type="primary",
            ):

                try:

                    delete_message(
                        message_id
                    )

                    st.session_state.messages = [
                        item
                        for item
                        in st.session_state.messages
                        if item["id"] != message_id
                    ]

                    st.success(
                        "Message deleted."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Failed to delete message: {e}"
                    )