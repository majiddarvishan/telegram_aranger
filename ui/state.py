from datetime import date,timedelta
import streamlit as st
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
        "message_date_range": (date.today() - timedelta(days=6), date.today()),
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


