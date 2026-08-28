from cryptography.fernet import Fernet
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

from services.telegram_runtime import get_runtime


def proxy_config(state) -> dict | None:
    if not state.get("use_proxy", True):
        return None
    proxy = {
        "scheme": "socks5",
        "hostname": state.get("proxy_host", "127.0.0.1"),
        "port": int(state.get("proxy_port", 1080)),
    }
    if state.get("proxy_user", "").strip():
        proxy["username"] = state["proxy_user"].strip()
    if state.get("proxy_pass", "").strip():
        proxy["password"] = state["proxy_pass"].strip()
    return proxy


def encrypt_session(key: str, session: str) -> bytes:
    return Fernet(key.encode()).encrypt(session.encode())


def decrypt_session(key: str, encrypted: bytes) -> str:
    return Fernet(key.encode()).decrypt(encrypted).decode()


def user_dict(user) -> dict:
    return {
        "id": user.id,
        "phone_number": user.phone_number or "",
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
    }


async def _new_client(settings, session_string=None, proxy=None):
    kwargs = {
        "name": "telegram",
        "api_id": settings.api_id,
        "api_hash": settings.api_hash,
        "proxy": proxy,
        "in_memory": True,
    }
    if session_string:
        kwargs["session_string"] = session_string
    client = Client(**kwargs)
    await client.connect()
    return client


async def _send_code(settings, phone, proxy):
    runtime = get_runtime()
    if runtime.client:
        try:
            await runtime.client.disconnect()
        except Exception:
            pass
        runtime.client = None
    client = await _new_client(settings, proxy=proxy)
    sent = await client.send_code(phone)
    runtime.client = client
    return sent.phone_code_hash


def send_code(settings, phone, proxy):
    return get_runtime().run(_send_code(settings, phone, proxy))


async def _verify_code(phone, code_hash, code):
    client = get_runtime().client
    try:
        await client.sign_in(phone, code_hash, code)
    except SessionPasswordNeeded:
        return "2fa", None
    return "success", user_dict(await client.get_me())


def verify_code(phone, code_hash, code):
    return get_runtime().run(_verify_code(phone, code_hash, code))


async def _verify_2fa(password):
    return user_dict(await get_runtime().client.check_password(password))


def verify_2fa(password):
    return get_runtime().run(_verify_2fa(password))


async def _export():
    return await get_runtime().client.export_session_string()


def export_session():
    return get_runtime().run(_export())


async def _restore(settings, encrypted, key, proxy):
    client = await _new_client(settings, decrypt_session(key, encrypted), proxy)
    try:
        me = await client.get_me()
        get_runtime().client = client
        return user_dict(me)
    except Exception:
        try:
            await client.disconnect()
        except Exception:
            pass
        raise


def restore(settings, encrypted, key, proxy):
    return get_runtime().run(_restore(settings, encrypted, key, proxy))


async def _disconnect(logout=False):
    runtime = get_runtime()
    client = runtime.client
    if not client:
        return
    try:
        if logout:
            await client.log_out()
        elif client.is_connected:
            await client.disconnect()
    finally:
        runtime.client = None


def disconnect():
    get_runtime().run(_disconnect(False))


def logout():
    get_runtime().run(_disconnect(True))


async def _dialogs():
    """Return Telegram dialogs without relying on version-specific Dialog attributes."""
    client = get_runtime().client
    if client is None:
        raise RuntimeError("Telegram client is not connected.")

    result = []

    async for dialog in client.get_dialogs():
        chat = dialog.chat
        chat_type = getattr(chat.type, "value", str(chat.type)).lower()

        if chat_type not in ("private", "group", "supergroup", "channel"):
            continue

        title = chat.title
        if not title:
            title = f"{chat.first_name or ''} {chat.last_name or ''}".strip()
        if not title:
            title = str(chat.id)

        result.append(
            {
                "id": chat.id,
                "title": title,
                "type": chat_type,
                "username": chat.username or "",
            }
        )

    return result


def get_dialogs():
    return get_runtime().run(_dialogs())


async def _history(chat_id, start_dt, end_dt, limit=100):
    client = get_runtime().client
    out = []

    async for message in client.get_chat_history(chat_id, limit=limit):
        if not message.date:
            continue
        if message.date < start_dt:
            break
        if message.date <= end_dt:
            out.append(
                {
                    "id": message.id,
                    "chat_id": chat_id,
                    "text": message.text or message.caption or "[Media / File]",
                    "date": message.date,
                    "user_id": chat_id,
                }
            )

    return out


def history(chat_id, start_dt, end_dt, limit=100):
    return get_runtime().run(_history(chat_id, start_dt, end_dt, limit))


async def _delete(chat_id, message_id):
    await get_runtime().client.delete_messages(chat_id, message_id)


def delete_message(chat_id, message_id):
    get_runtime().run(_delete(chat_id, message_id))
