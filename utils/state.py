from datetime import date, timedelta
import streamlit as st

def initialize_state():
    today=date.today()
    defaults={
        "web_user":None,"telegram_runtime":None,"telegram_login_active":False,"telegram_login_stage":"phone",
        "telegram_login_phone":"","telegram_phone_code_hash":"","telegram_user":None,
        "selected_telegram_account_id":None,"selected_chat_id":None,"dialogs":[],"messages":[],
        "use_proxy":True,"proxy_host":"127.0.0.1","proxy_port":1080,"proxy_user":"","proxy_pass":"",
        "message_date_range":(today-timedelta(days=6),today),"page_anchor":today,
    }
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v
