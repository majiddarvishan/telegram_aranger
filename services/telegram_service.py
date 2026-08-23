from datetime import date
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
from config.settings import API_ID,API_HASH
from services.auth_service import decrypt_session
from runtime.telegram_runtime import get_runtime
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


async def fetch_saved_messages_for_range_async(start_date: date,end_date: date,limit:int=10000)->list[dict]:
 if end_date<start_date: raise ValueError("End date cannot be earlier than start date.")
 client=get_runtime_client(); me=await client.get_me(); messages=[]
 async for message in client.get_chat_history("me",limit=limit):
  d=message.date.date()
  if d>end_date: continue
  if d<start_date: break
  messages.append({"id":message.id,"text":message.text or message.caption or "[Media / File]","date":str(message.date),"user_id":me.id})
 return messages
def fetch_saved_messages_for_range(start_date:date,end_date:date,limit:int=10000):
 return get_runtime().run(fetch_saved_messages_for_range_async(start_date,end_date,limit))
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


