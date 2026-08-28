# Python 3.14 compatibility: Pyrogram imports asyncio.get_event_loop() at import time.
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

import streamlit as st

from config.settings import load_settings
from db.database import initialize_database
from services.telegram_runtime import get_runtime
from ui.auth import render_web_auth
from ui.main import render_main
from ui.sidebar import render_sidebar
from utils.state import initialize_state


st.set_page_config(page_title="Telegram Saved Messages Manager", layout="wide")

settings = load_settings()
initialize_database(settings.db_file)
initialize_state()

if st.session_state.web_user is None:
    render_web_auth(settings)
    st.stop()

render_sidebar(settings)
render_main(settings)
