import os
import streamlit as st
from dotenv import load_dotenv
from cryptography.fernet import Fernet
load_dotenv()
def get_config(name):
    v=os.getenv(name)
    if not v:
        try:v=st.secrets[name]
        except Exception:v=None
    if not v: raise RuntimeError(f"Required configuration {name!r} is not set.")
    return v
API_ID=int(get_config("TELEGRAM_API_ID"))
API_HASH=get_config("TELEGRAM_API_HASH")
SESSION_ENCRYPTION_KEY=get_config("TELEGRAM_SESSION_ENCRYPTION_KEY").strip().encode()
Fernet(SESSION_ENCRYPTION_KEY)
