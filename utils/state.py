from datetime import date, timedelta

import streamlit as st


def initialize_state():
    today = date.today()
    defaults = {
        "web_user": None,
        "remember_token": None,
        "telegram_runtime": None,
        "telegram_login_active": False,
        "telegram_login_stage": "phone",
        "telegram_login_phone": "",
        "telegram_phone_code_hash": "",
        "telegram_user": None,
        "selected_telegram_account_id": None,
        "selected_chat_id": None,
        "dialogs": [],
        "force_refresh_dialogs": False,
        "messages": [],
        "message_query_signature": None,
        "message_range_signature": None,
        "message_result_limit": None,
        "message_fetch_error": None,
        "message_auto_latest_chat_id": None,
        "media_files": {},
        "pending_delete_message": None,
        "use_proxy": True,
        "proxy_host": "127.0.0.1",
        "proxy_port": 1080,
        "proxy_user": "",
        "proxy_pass": "",
        "message_date_range": (today - timedelta(days=6), today),
        "message_date_range_picker": (today - timedelta(days=6), today),
        "pending_message_date_range": None,
        "page_anchor": today,
        "workspace": "Telegram Messages",
        "youtube_url": "",
        "youtube_inspected_url": "",
        "youtube_metadata": None,
        "youtube_error": None,
        "youtube_download_result": None,
        "youtube_mode": "Video + Audio",
        "youtube_quality_key": "best",
        "youtube_subtitles_enabled": False,
        "youtube_subtitle_index": 0,
        "youtube_save_directory": "",
        "youtube_create_directory": False,
        "youtube_acknowledged": False,
        "youtube_use_proxy": False,
        "youtube_proxy_host": "127.0.0.1",
        "youtube_proxy_port": 1080,
        "youtube_proxy_user": "",
        "youtube_proxy_pass": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
