import streamlit as st
from db.telegram_accounts import list_accounts, get_account, save_account, delete_account
from services.telegram_service import proxy_config, send_code, verify_code, verify_2fa, export_session, restore, disconnect, logout, get_dialogs
from pyrogram.errors import PhoneCodeExpired, PhoneCodeInvalid, PhoneNumberInvalid, PasswordHashInvalid


def _reset_login():
    st.session_state.telegram_login_active=False; st.session_state.telegram_login_stage="phone"; st.session_state.telegram_login_phone=""; st.session_state.telegram_phone_code_hash=""

def _start_login():
    _reset_login(); st.session_state.telegram_login_active=True; st.session_state.telegram_user=None; st.session_state.messages=[]


def render_sidebar(settings):
    user=st.session_state.web_user
    st.sidebar.title("👤 Account"); st.sidebar.write(f"**{user['display_name']}**"); st.sidebar.caption(f"@{user['username']}")
    if st.sidebar.button("🚪 Logout Web Application",use_container_width=True):
        try:
            if st.session_state.get("telegram_runtime"): st.session_state.telegram_runtime.stop()
        except Exception: pass
        st.session_state.clear(); st.rerun()
    st.sidebar.markdown("---"); st.sidebar.header("⚙️ Network Settings")
    st.session_state.use_proxy=st.sidebar.checkbox("Enable SOCKS5 Proxy",value=st.session_state.use_proxy)
    if st.session_state.use_proxy:
        st.session_state.proxy_host=st.sidebar.text_input("Proxy Host/IP",value=st.session_state.proxy_host)
        st.session_state.proxy_port=st.sidebar.number_input("Proxy Port",value=st.session_state.proxy_port,min_value=1,max_value=65535)
        st.session_state.proxy_user=st.sidebar.text_input("Username (Optional)",value=st.session_state.proxy_user)
        st.session_state.proxy_pass=st.sidebar.text_input("Password (Optional)",type="password",value=st.session_state.proxy_pass)
    proxy=proxy_config(st.session_state)
    st.sidebar.markdown("---"); st.sidebar.header("📱 Telegram Accounts")
    accounts=list_accounts(settings.db_file,user["id"])
    if st.sidebar.button("➕ Add Telegram Account",use_container_width=True): _start_login(); st.rerun()
    if accounts:
        labels={a["id"]:(f"@{a['username']}" if a["username"] else ((a["first_name"]+" "+a["last_name"]).strip() or str(a["telegram_user_id"]))) for a in accounts}
        current=st.session_state.selected_telegram_account_id
        if current not in labels: current=next(iter(labels)); st.session_state.selected_telegram_account_id=current
        selected=st.sidebar.selectbox("Active Telegram Account",list(labels),index=list(labels).index(current),format_func=lambda x:labels[x])
        if selected!=st.session_state.selected_telegram_account_id:
            st.session_state.selected_telegram_account_id=selected; st.session_state.selected_chat_id=None; st.session_state.messages=[]; st.session_state.telegram_user=None; disconnect(); st.rerun()
    account_id=st.session_state.selected_telegram_account_id
    if account_id and not st.session_state.telegram_login_active and not st.session_state.telegram_user:
        account=get_account(settings.db_file,user["id"],account_id)
        if account:
            try:
                with st.spinner("Connecting to Telegram..."): st.session_state.telegram_user=restore(settings,account["encrypted_session"],settings.session_encryption_key,proxy)
            except Exception as e: st.sidebar.error(f"Failed to restore Telegram session: {e}")
    if st.session_state.telegram_user:
        tg=st.session_state.telegram_user; st.sidebar.success("🟢 Telegram Connected"); st.sidebar.caption(f"{tg['first_name']} {tg['last_name']}".strip()); st.sidebar.caption(f"ID: {tg['id']}")
        if st.sidebar.button("🔌 Disconnect Telegram",use_container_width=True): disconnect(); st.session_state.telegram_user=None; st.session_state.messages=[]; st.rerun()
        if st.sidebar.button("🚪 Logout Telegram Account",use_container_width=True):
            try: logout()
            finally: delete_account(settings.db_file,user["id"],account_id); st.session_state.telegram_user=None; st.session_state.selected_telegram_account_id=None; st.session_state.selected_chat_id=None; st.session_state.messages=[]; st.rerun()
        if st.sidebar.button("🔄 Refresh Chats",use_container_width=True): st.session_state.dialogs=[]; st.rerun()
    if st.session_state.telegram_login_active and not st.session_state.telegram_user:
        st.sidebar.markdown("---"); st.sidebar.header("🔐 Add Telegram Account")
        stage=st.session_state.telegram_login_stage
        if stage=="phone":
            with st.sidebar.form("tg_phone"):
                phone=st.text_input("Phone Number",placeholder="+989123456789"); ok=st.form_submit_button("📱 Send Login Code",use_container_width=True)
            if ok:
                try:
                    h=send_code(settings,phone.strip(),proxy); st.session_state.telegram_login_phone=phone.strip(); st.session_state.telegram_phone_code_hash=h; st.session_state.telegram_login_stage="code"; st.rerun()
                except Exception as e: st.sidebar.error(f"Failed to send code: {e}")
        elif stage=="code":
            st.sidebar.info(f"Code sent to {st.session_state.telegram_login_phone}")
            with st.sidebar.form("tg_code"):
                code=st.text_input("Telegram Code"); ok=st.form_submit_button("✅ Verify Code",use_container_width=True)
            if ok:
                try:
                    status,tg=verify_code(st.session_state.telegram_login_phone,st.session_state.telegram_phone_code_hash,code.strip())
                    if status=="2fa": st.session_state.telegram_login_stage="2fa"; st.rerun()
                    else:
                        aid=save_account(settings.db_file,user["id"],tg, __import__('services.telegram_service',fromlist=['encrypt_session']).encrypt_session(settings.session_encryption_key,export_session()))
                        st.session_state.telegram_user=tg; st.session_state.selected_telegram_account_id=aid; _reset_login(); st.rerun()
                except PhoneCodeExpired: st.sidebar.error("The Telegram code has expired. Request a new code.")
                except PhoneCodeInvalid: st.sidebar.error("The Telegram code is invalid.")
                except PhoneNumberInvalid: st.sidebar.error("The Telegram phone number is invalid.")
                except Exception as e: st.sidebar.error(f"Code verification failed: {e}")
            if st.sidebar.button("🔄 Resend Code",use_container_width=True):
                try: st.session_state.telegram_phone_code_hash=send_code(settings,st.session_state.telegram_login_phone,proxy); st.rerun()
                except Exception as e: st.sidebar.error(f"Failed to resend code: {e}")
            if st.sidebar.button("↩️ Change Phone Number",use_container_width=True): _reset_login(); st.session_state.telegram_login_active=True; st.rerun()
        else:
            st.sidebar.info("This account has Two-Step Verification enabled.")
            with st.sidebar.form("tg_2fa"):
                password=st.text_input("Telegram 2FA Password",type="password"); ok=st.form_submit_button("🔓 Login",use_container_width=True)
            if ok:
                try:
                    tg=verify_2fa(password); aid=save_account(settings.db_file,user["id"],tg,__import__('services.telegram_service',fromlist=['encrypt_session']).encrypt_session(settings.session_encryption_key,export_session())); st.session_state.telegram_user=tg; st.session_state.selected_telegram_account_id=aid; _reset_login(); st.rerun()
                except PasswordHashInvalid: st.sidebar.error("The Telegram 2FA password is incorrect.")
                except Exception as e: st.sidebar.error(f"2FA verification failed: {e}")
    return proxy
