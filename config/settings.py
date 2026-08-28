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
    return Settings(api_id=api_id, api_hash=api_hash, session_encryption_key=key,
                    db_file=os.getenv("TELEGRAM_DB_FILE", "telegram_manager.db"))
