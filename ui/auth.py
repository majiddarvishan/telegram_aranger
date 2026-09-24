from datetime import datetime, timedelta, timezone

import extra_streamlit_components as stx
import streamlit as st

from db.auth_sessions import create_session, delete_session, get_user_by_session
from db.users import authenticate_user, create_user

COOKIE_NAME = "telegram_manager_remember"


def get_cookie_manager():
    """Return one CookieManager instance per Streamlit browser session.

    CookieManager is a Streamlit custom component. Creating it more than once
    during the same script run with the same key raises
    StreamlitDuplicateElementKey. Keeping the instance in session_state avoids
    duplicate component registration while still isolating it per Web session.
    """
    manager = st.session_state.get("_cookie_manager")
    if manager is None:
        manager = stx.CookieManager(key="telegram_manager_auth_cookie")
        st.session_state._cookie_manager = manager
    return manager


def restore_remembered_user(settings) -> bool:
    """Restore the Web user from the persistent browser cookie, if present.

    CookieManager is a custom Streamlit component. On a fresh browser/server
    session its first render can return the component default before browser
    cookies have arrived. Because the manager instance is intentionally kept in
    session_state, relying on manager.get() would keep that initial snapshot
    forever. Refresh the cookie snapshot explicitly on every restore attempt.
    """
    if st.session_state.get("web_user") is not None:
        return True

    cookie_manager = get_cookie_manager()
    cookies = cookie_manager.get_all(key="restore_remember_cookies") or {}

    hydrated = st.session_state.get("_remember_cookie_hydrated", False)
    if not hydrated:
        st.session_state._remember_cookie_hydrated = True
        if COOKIE_NAME not in cookies:
            # Give the browser-side component one rerun to hydrate persisted
            # cookies before deciding that no remembered login exists.
            st.stop()

    token = cookies.get(COOKIE_NAME)
    if not token:
        return False

    user = get_user_by_session(settings.db_file, token)
    if not user:
        try:
            cookie_manager.delete(COOKIE_NAME, key="delete_invalid_remember_cookie")
        except Exception:
            pass
        return False

    st.session_state.web_user = user
    st.session_state.remember_token = token
    return True


def _clear_remember_cookie(settings) -> None:
    token = st.session_state.pop("remember_token", None)
    cookie_manager = get_cookie_manager()

    try:
        cookies = cookie_manager.get_all(key="clear_remember_cookies") or {}
    except Exception:
        cookies = {}

    browser_token = cookies.get(COOKIE_NAME)
    token_to_revoke = token or browser_token
    if token_to_revoke:
        delete_session(settings.db_file, token_to_revoke)

    if browser_token:
        try:
            cookie_manager.delete(
                COOKIE_NAME,
                key="delete_remember_cookie",
            )
        except Exception:
            pass


def logout_web_user(settings) -> None:
    """Revoke the current persistent login and clear Web session state."""
    _clear_remember_cookie(settings)
    st.session_state.clear()


def _create_remember_session(settings, user: dict) -> None:
    token = create_session(settings.db_file, user["id"], settings.remember_me_days)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.remember_me_days)
    get_cookie_manager().set(
        COOKIE_NAME,
        token,
        key="set_remember_cookie",
        path="/",
        expires_at=expires_at,
        secure=None,
        max_age=settings.remember_me_days * 24 * 60 * 60,
        same_site="lax",
    )
    st.session_state.remember_token = token


def render_web_auth(settings):
    st.title("🔐 Telegram Saved Messages Manager")
    login, register = st.tabs(["Login", "Create Account"])

    with login:
        with st.form("web_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            remember_me = st.checkbox(
                f"Remember me for {settings.remember_me_days} days",
                value=True,
            )
            submit = st.form_submit_button("Login", use_container_width=True)

        if submit:
            user = authenticate_user(settings.db_file, username, password)
            if not user:
                st.error("Invalid username or password.")
            else:
                if remember_me:
                    _create_remember_session(settings, user)
                else:
                    _clear_remember_cookie(settings)
                st.session_state.web_user = user
                st.rerun()

    with register:
        with st.form("web_register"):
            name = st.text_input("Display Name")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Create Account", use_container_width=True)

        if submit:
            if len(password) < 8:
                st.error("Password must contain at least 8 characters.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif not username.strip():
                st.error("Username is required.")
            elif create_user(settings.db_file, username, password, name):
                st.success("Account created. You can now login.")
            else:
                st.error("Username already exists.")
