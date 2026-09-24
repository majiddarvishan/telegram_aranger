from dataclasses import dataclass
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    session_encryption_key: str
    db_file: str = "telegram_manager.db"
    default_message_limit: int = 100
    remember_me_days: int = 7
    media_cache_dir: str = ".cache/telegram_media"
    media_cache_ttl_hours: int = 24
    media_cache_max_mb: int = 2048
    media_preview_max_mb: int = 200
    media_download_max_mb: int = 200


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        try:
            value = st.secrets[name]
        except Exception:
            value = None
    if not value:
        raise RuntimeError(f"Required configuration '{name}' is not set.")
    return str(value).strip()


def load_settings() -> Settings:
    api_id = int(_required("TELEGRAM_API_ID"))
    api_hash = _required("TELEGRAM_API_HASH")
    key = _required("TELEGRAM_SESSION_ENCRYPTION_KEY")
    from cryptography.fernet import Fernet
    try:
        Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError(
            "TELEGRAM_SESSION_ENCRYPTION_KEY is invalid. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc
    try:
        remember_me_days = int(os.getenv("WEB_REMEMBER_ME_DAYS", "7"))
        media_cache_ttl_hours = int(os.getenv("MEDIA_CACHE_TTL_HOURS", "24"))
        media_cache_max_mb = int(os.getenv("MEDIA_CACHE_MAX_MB", "2048"))
        media_preview_max_mb = int(os.getenv("MEDIA_PREVIEW_MAX_MB", "200"))
        media_download_max_mb = int(os.getenv("MEDIA_DOWNLOAD_MAX_MB", "200"))
    except ValueError as exc:
        raise RuntimeError(
            "WEB_REMEMBER_ME_DAYS and MEDIA_* numeric settings must be integers."
        ) from exc

    if remember_me_days < 1:
        raise RuntimeError("WEB_REMEMBER_ME_DAYS must be greater than zero.")
    if media_cache_ttl_hours < 0:
        raise RuntimeError("MEDIA_CACHE_TTL_HOURS must be zero or greater.")
    if media_cache_max_mb < 0:
        raise RuntimeError("MEDIA_CACHE_MAX_MB must be zero or greater.")
    if media_preview_max_mb < 1:
        raise RuntimeError("MEDIA_PREVIEW_MAX_MB must be greater than zero.")
    if media_download_max_mb < 1:
        raise RuntimeError("MEDIA_DOWNLOAD_MAX_MB must be greater than zero.")

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        session_encryption_key=key,
        db_file=os.getenv("TELEGRAM_DB_FILE", "telegram_manager.db"),
        remember_me_days=remember_me_days,
        media_cache_dir=os.getenv("MEDIA_CACHE_DIR", ".cache/telegram_media"),
        media_cache_ttl_hours=media_cache_ttl_hours,
        media_cache_max_mb=media_cache_max_mb,
        media_preview_max_mb=media_preview_max_mb,
        media_download_max_mb=media_download_max_mb,
    )
