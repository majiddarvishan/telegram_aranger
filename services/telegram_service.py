import secrets
import threading

from cryptography.fernet import Fernet
from pyrogram import Client, raw
from pyrogram.errors import PeerIdInvalid, SessionPasswordNeeded

from services.media_cache import (
    atomic_replace_download,
    cache_path,
    cleanup_cache,
    is_valid_cached_file,
    safe_file_name,
)
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


async def _send_code(runtime, settings, phone, proxy):
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
    runtime = get_runtime()
    return runtime.run(
        _send_code(runtime, settings, phone, proxy),
        operation="send_code",
    )


async def _verify_code(client, phone, code_hash, code):
    try:
        await client.sign_in(phone, code_hash, code)
    except SessionPasswordNeeded:
        return "2fa", None
    return "success", user_dict(await client.get_me())


def verify_code(phone, code_hash, code):
    runtime = get_runtime()
    return runtime.run(
        _verify_code(runtime.client, phone, code_hash, code),
        operation="verify_code",
    )


async def _verify_2fa(client, password):
    return user_dict(await client.check_password(password))


def verify_2fa(password):
    runtime = get_runtime()
    return runtime.run(
        _verify_2fa(runtime.client, password),
        operation="verify_2fa",
    )


async def _export(client):
    return await client.export_session_string()


def export_session():
    runtime = get_runtime()
    return runtime.run(
        _export(runtime.client),
        operation="export_session",
    )


async def _hydrate_peer_cache(
    client,
    peer_records: list[tuple[int, int, str, str, str]] | None,
) -> None:
    """Restore persisted Pyrogram peers into the in-memory session."""
    if not peer_records:
        return
    await client.storage.update_peers(peer_records)


async def _restore(
    runtime,
    settings,
    encrypted,
    key,
    proxy,
    peer_records=None,
):
    client = await _new_client(settings, decrypt_session(key, encrypted), proxy)
    try:
        await _hydrate_peer_cache(client, peer_records)
        me = await client.get_me()
        runtime.client = client
        return user_dict(me)
    except Exception:
        try:
            await client.disconnect()
        except Exception:
            pass
        raise


def restore(settings, encrypted, key, proxy, peer_records=None):
    runtime = get_runtime()
    return runtime.run(
        _restore(
            runtime,
            settings,
            encrypted,
            key,
            proxy,
            peer_records=peer_records,
        ),
        operation="restore_session",
    )


async def _disconnect(runtime, logout=False):
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
    runtime = get_runtime()
    runtime.run(
        _disconnect(runtime, False),
        operation="disconnect",
    )


def logout():
    runtime = get_runtime()
    runtime.run(
        _disconnect(runtime, True),
        operation="logout",
    )


def _peer_record_from_input_peer(
    chat_id: int,
    chat_type: str,
    username: str,
    input_peer,
) -> dict:
    """Normalize a resolved Pyrogram InputPeer for persistent caching."""
    if isinstance(input_peer, raw.types.InputPeerChannel):
        peer_type = (
            chat_type
            if chat_type in ("channel", "supergroup")
            else "channel"
        )
        access_hash = int(input_peer.access_hash)
    elif isinstance(input_peer, raw.types.InputPeerUser):
        peer_type = "user"
        access_hash = int(input_peer.access_hash)
    elif isinstance(input_peer, raw.types.InputPeerChat):
        peer_type = "group"
        access_hash = 0
    else:
        return {
            "peer_access_hash": None,
            "peer_type": "",
        }

    return {
        "peer_access_hash": access_hash,
        "peer_type": peer_type,
    }


async def _dialogs(client, limit: int):
    """Return Telegram dialogs without relying on version-specific Dialog attributes."""
    if client is None:
        raise RuntimeError("Telegram client is not connected.")

    result = []

    async for dialog in client.get_dialogs(limit=limit):
        chat = dialog.chat
        chat_type = getattr(chat.type, "value", str(chat.type)).lower()

        if chat_type not in ("private", "group", "supergroup", "channel"):
            continue

        title = chat.title
        if not title:
            title = f"{chat.first_name or ''} {chat.last_name or ''}".strip()
        if not title:
            title = str(chat.id)

        username = chat.username or ""
        input_peer = await client.resolve_peer(chat.id)
        peer_record = _peer_record_from_input_peer(
            chat.id,
            chat_type,
            username,
            input_peer,
        )

        result.append(
            {
                "id": chat.id,
                "title": title,
                "type": chat_type,
                "username": username,
                **peer_record,
            }
        )

    return result


def get_dialogs(limit: int):
    runtime = get_runtime()
    return runtime.run(
        _dialogs(runtime.client, limit),
        operation="get_dialogs",
    )


_MEDIA_FIELDS = (
    ("photo", "photo"),
    ("video", "video"),
    ("animation", "animation"),
    ("document", "document"),
    ("audio", "audio"),
    ("voice", "voice"),
    ("video_note", "video_note"),
)


def _media_metadata(message) -> dict | None:
    """Return normalized Telegram media metadata without downloading the media."""
    for media_type, attribute in _MEDIA_FIELDS:
        media = getattr(message, attribute, None)
        if media is None:
            continue

        file_name = getattr(media, "file_name", None)
        mime_type = getattr(media, "mime_type", None)
        if not mime_type:
            mime_type = {
                "photo": "image/jpeg",
                "video": "video/mp4",
                "video_note": "video/mp4",
                "voice": "audio/ogg",
            }.get(media_type)
        file_size = getattr(media, "file_size", None)
        width = getattr(media, "width", None)
        height = getattr(media, "height", None)
        duration = getattr(media, "duration", None)

        return {
            "type": media_type,
            "file_id": getattr(media, "file_id", None),
            "file_unique_id": getattr(media, "file_unique_id", None),
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": file_size,
            "width": width,
            "height": height,
            "duration": duration,
        }

    return None


def _message_text(message, media: dict | None) -> str:
    if message.text:
        return message.text
    if message.caption:
        return message.caption
    if media:
        return f"[{media['type'].replace('_', ' ').title()}]"
    return "[Message]"


async def _warm_peer_for_history(
    client,
    chat_id: int,
    username: str = "",
    dialog_limit: int = 100,
) -> None:
    """Populate Pyrogram's in-memory peer cache for a cached dialog."""
    if client is None:
        raise RuntimeError("Telegram client is not connected.")

    if username:
        try:
            await client.get_chat(username)
            return
        except Exception:
            # Some private chats/groups have stale or unavailable usernames.
            # Fall back to a bounded dialog refresh below.
            pass

    async for _ in client.get_dialogs(limit=dialog_limit):
        pass

    # Raise PeerIdInvalid here if the selected cached dialog is no longer
    # reachable even after refreshing Pyrogram's peer cache.
    await client.resolve_peer(chat_id)


async def _history(chat_id, start_dt, end_dt, limit=100, client=None):
    if client is None:
        raise RuntimeError("Telegram client is not connected.")

    out = []

    # Start at the requested range end instead of taking only the newest N
    # messages in the chat. Pyrogram returns history in reverse chronological
    # order, so we can stop as soon as the range start is crossed.
    async for message in client.get_chat_history(
        chat_id,
        limit=0,
        offset_date=end_dt,
    ):
        if not message.date:
            continue
        if message.date < start_dt:
            break
        if message.date > end_dt:
            continue

        media = _media_metadata(message)
        out.append(
            {
                "id": message.id,
                "chat_id": chat_id,
                "text": _message_text(message, media),
                "caption": message.caption or "",
                "date": message.date,
                "user_id": chat_id,
                "media": media,
            }
        )

        if limit and len(out) >= limit:
            break

    return out


async def _history_with_peer_recovery(
    client,
    chat_id,
    start_dt,
    end_dt,
    limit=100,
    peer_username: str = "",
    dialog_limit: int = 100,
):
    try:
        return await _history(
            chat_id,
            start_dt,
            end_dt,
            limit,
            client=client,
        )
    except PeerIdInvalid:
        await _warm_peer_for_history(
            client,
            chat_id,
            username=peer_username,
            dialog_limit=dialog_limit,
        )
        return await _history(
            chat_id,
            start_dt,
            end_dt,
            limit,
            client=client,
        )


def history(
    chat_id,
    start_dt,
    end_dt,
    limit=100,
    peer_username: str = "",
    dialog_limit: int = 100,
):
    runtime = get_runtime()
    return runtime.run(
        _history_with_peer_recovery(
            runtime.client,
            chat_id,
            start_dt,
            end_dt,
            limit,
            peer_username=peer_username,
            dialog_limit=dialog_limit,
        ),
        operation="history",
    )


class MediaDownloadProgress:
    def __init__(self):
        self._lock = threading.Lock()
        self._current = 0
        self._total = 0

    async def update(self, current: int, total: int):
        with self._lock:
            self._current = int(current or 0)
            self._total = int(total or 0)

    def snapshot(self) -> tuple[int, int]:
        with self._lock:
            return self._current, self._total


def _size_limit_bytes(max_megabytes: int) -> int:
    return max_megabytes * 1024 * 1024


async def _download_media(
    client,
    chat_id: int,
    message_id: int,
    account_id: int,
    cache_root: str,
    cache_ttl_hours: int,
    cache_max_mb: int,
    max_megabytes: int,
    progress_callback=None,
    force_download: bool = False,
):
    if client is None:
        raise RuntimeError("Telegram client is not connected.")

    message = await client.get_messages(chat_id, message_ids=message_id)
    if message is None:
        raise RuntimeError("Telegram message was not found.")

    media = _media_metadata(message)
    if not media:
        raise ValueError("Message does not contain downloadable media.")

    file_size = media.get("file_size")
    if file_size and file_size > _size_limit_bytes(max_megabytes):
        raise ValueError(
            f"Media is too large ({file_size / (1024 * 1024):.1f} MB). "
            f"The configured limit is {max_megabytes} MB."
        )

    cleanup_cache(cache_root, cache_ttl_hours, cache_max_mb)

    fallback = f"{media['type']}_{message_id}"
    download_name = safe_file_name(
        media.get("file_name"),
        fallback=fallback,
        mime_type=media.get("mime_type"),
    )
    unique_prefix = safe_file_name(
        media.get("file_unique_id"),
        fallback="telegram",
    )
    cached_name = f"{unique_prefix}_{download_name}"

    final_path = cache_path(
        cache_root=cache_root,
        account_id=account_id,
        chat_id=chat_id,
        message_id=message_id,
        media_type=media["type"],
        file_name=cached_name,
    )

    if force_download and final_path.exists():
        try:
            final_path.unlink()
        except OSError as exc:
            raise RuntimeError(
                "Cached media could not be removed for a forced re-download."
            ) from exc

    if is_valid_cached_file(
        final_path,
        cache_ttl_hours,
        expected_size=file_size,
    ):
        return {
            "path": str(final_path),
            "file_name": download_name,
            "mime_type": media.get("mime_type") or "application/octet-stream",
            "file_size": final_path.stat().st_size,
            "media_type": media["type"],
            "cached": True,
        }

    if final_path.exists():
        try:
            final_path.unlink()
        except OSError as exc:
            raise RuntimeError(
                "Cached media is invalid and could not be removed for retry."
            ) from exc

    final_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = final_path.with_name(
        f".{final_path.name}.{secrets.token_hex(6)}.part"
    )

    try:
        downloaded = await client.download_media(
            message,
            file_name=str(temporary_path),
            in_memory=False,
            progress=progress_callback,
        )
        if not downloaded:
            raise RuntimeError("Telegram media download did not complete.")

        final_path = atomic_replace_download(downloaded, final_path)

        if file_size and final_path.stat().st_size != file_size:
            final_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Telegram media download completed with an unexpected file size. "
                "The incomplete cache file was removed; retry the download."
            )
    finally:
        temporary_path.unlink(missing_ok=True)

    return {
        "path": str(final_path),
        "file_name": download_name,
        "mime_type": media.get("mime_type") or "application/octet-stream",
        "file_size": final_path.stat().st_size,
        "media_type": media["type"],
        "cached": False,
    }


def start_media_download(
    chat_id: int,
    message_id: int,
    account_id: int,
    settings,
    max_megabytes: int,
    force_download: bool = False,
):
    runtime = get_runtime()
    progress = MediaDownloadProgress()
    future = runtime.submit(
        _download_media(
            client=runtime.client,
            chat_id=chat_id,
            message_id=message_id,
            account_id=account_id,
            cache_root=settings.media_cache_dir,
            cache_ttl_hours=settings.media_cache_ttl_hours,
            cache_max_mb=settings.media_cache_max_mb,
            max_megabytes=max_megabytes,
            progress_callback=progress.update,
            force_download=force_download,
        )
    )
    return future, progress


def download_media(
    chat_id: int,
    message_id: int,
    account_id: int,
    settings,
    max_megabytes: int,
    force_download: bool = False,
):
    future, _ = start_media_download(
        chat_id=chat_id,
        message_id=message_id,
        account_id=account_id,
        settings=settings,
        max_megabytes=max_megabytes,
        force_download=force_download,
    )
    return future.result()


async def _delete(client, chat_id, message_id):
    await client.delete_messages(chat_id, message_id)


def delete_message(chat_id, message_id):
    runtime = get_runtime()
    runtime.run(
        _delete(runtime.client, chat_id, message_id),
        operation="delete_message",
    )
