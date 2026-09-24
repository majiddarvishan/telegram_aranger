# Python 3.14 compatibility: Pyrogram imports asyncio.get_event_loop() at import time.
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import logging

import streamlit as st

from config.settings import load_settings
from db.auth_sessions import cleanup_expired_sessions
from db.database import initialize_database
from services.telegram_runtime import get_runtime
from ui.auth import render_web_auth, restore_remembered_user
from ui.main import render_main
from ui.sidebar import render_sidebar
from utils.logging import configure_logging, log_event
from utils.state import initialize_state


st.set_page_config(page_title="Telegram Saved Messages Manager", layout="wide")

configure_logging()
logger = logging.getLogger("telegram_aranger.app")

settings = load_settings()
initialize_database(settings.db_file)
expired_sessions = cleanup_expired_sessions(settings.db_file)
initialize_state()

log_event(
    logger,
    "application_ready",
    db_file=settings.db_file,
    expired_sessions_removed=expired_sessions,
)

if st.session_state.web_user is None:
    restore_remembered_user(settings)

if st.session_state.web_user is None:
    render_web_auth(settings)
    st.stop()

render_sidebar(settings)
render_main(settings)
