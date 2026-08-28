import streamlit as st
from db.users import authenticate_user, create_user

def render_web_auth(settings):
    st.title("🔐 Telegram Saved Messages Manager")
    login, register = st.tabs(["Login","Create Account"])
    with login:
        with st.form("web_login"):
            u=st.text_input("Username"); p=st.text_input("Password",type="password")
            submit=st.form_submit_button("Login",use_container_width=True)
        if submit:
            user=authenticate_user(settings.db_file,u,p)
            if user: st.session_state.web_user=user; st.rerun()
            else: st.error("Invalid username or password.")
    with register:
        with st.form("web_register"):
            name=st.text_input("Display Name"); u=st.text_input("Username"); p=st.text_input("Password",type="password"); cp=st.text_input("Confirm Password",type="password")
            submit=st.form_submit_button("Create Account",use_container_width=True)
        if submit:
            if len(p)<8: st.error("Password must contain at least 8 characters.")
            elif p!=cp: st.error("Passwords do not match.")
            elif not u.strip(): st.error("Username is required.")
            elif create_user(settings.db_file,u,p,name): st.success("Account created. You can now login.")
            else: st.error("Username already exists.")
