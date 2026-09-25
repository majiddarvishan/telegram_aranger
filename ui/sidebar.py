import streamlit as st
from pyrogram.errors import (
    PasswordHashInvalid,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
)

from config.branding import PRODUCT_NAME, PRODUCT_VERSION
from db.dialogs import load_peer_records
from db.telegram_accounts import (
    delete_account,
    get_account,
    list_accounts,
    save_account,
)
from services.telegram_service import (
    disconnect,
    encrypt_session,
    export_session,
    logout,
    proxy_config,
    restore,
    send_code,
    verify_2fa,
    verify_code,
)
from ui.auth import logout_web_user
from ui.theme import (
    account_card_html,
    badge_html,
    section_title_html,
    sidebar_brand_html,
)


WEB_ACCOUNT_CARD_KEY = "web-account-card"


def _reset_login() -> None:
    st.session_state.telegram_login_active = False
    st.session_state.telegram_login_stage = "phone"
    st.session_state.telegram_login_phone = ""
    st.session_state.telegram_phone_code_hash = ""


def _start_login() -> None:
    _reset_login()
    st.session_state.telegram_login_active = True
    st.session_state.telegram_user = None
    st.session_state.messages = []


def _apply_account_selection(
    state,
    selected_account_id: int,
) -> bool:
    """Apply the pure state transition for switching Telegram accounts."""
    if selected_account_id == state.get("selected_telegram_account_id"):
        return False

    state["selected_telegram_account_id"] = selected_account_id
    state["selected_chat_id"] = None
    state["messages"] = []
    state["message_fetch_error"] = None
    state["message_auto_latest_chat_id"] = None
    state["dialogs"] = []
    state["force_refresh_dialogs"] = False
    state["telegram_user"] = None
    state["media_files"] = {}
    return True


def _render_brand() -> None:
    st.sidebar.markdown(
        sidebar_brand_html(PRODUCT_NAME, PRODUCT_VERSION),
        unsafe_allow_html=True,
    )


def _render_web_account(settings, user: dict) -> None:
    display_name = user.get("display_name") or user["username"]
    st.sidebar.markdown(
        section_title_html("Web account"),
        unsafe_allow_html=True,
    )

    with st.sidebar.container(
        border=True,
        key=WEB_ACCOUNT_CARD_KEY,
    ):
        st.markdown(
            account_card_html(display_name, user["username"]),
            unsafe_allow_html=True,
        )

        if st.button(
            "Sign out",
            key="sidebar-web-logout",
            use_container_width=False,
        ):
            try:
                runtime = st.session_state.get("telegram_runtime")
                if runtime:
                    runtime.stop()
            except Exception:
                pass

            logout_web_user(settings)
            # Cookie deletion is browser-side. Let the component finish naturally.
            st.stop()


def _render_network_settings():
    proxy_tone = "info" if st.session_state.use_proxy else "neutral"
    proxy_label = "Proxy on" if st.session_state.use_proxy else "Proxy off"

    with st.sidebar.expander(
        "Network & proxy",
        expanded=False,
    ):
        st.markdown(
            badge_html(proxy_label, proxy_tone),
            unsafe_allow_html=True,
        )
        st.session_state.use_proxy = st.checkbox(
            "Enable SOCKS5 proxy",
            value=st.session_state.use_proxy,
        )

        if st.session_state.use_proxy:
            st.session_state.proxy_host = st.text_input(
                "Proxy host / IP",
                value=st.session_state.proxy_host,
            )
            st.session_state.proxy_port = st.number_input(
                "Proxy port",
                value=st.session_state.proxy_port,
                min_value=1,
                max_value=65535,
            )
            st.session_state.proxy_user = st.text_input(
                "Username (optional)",
                value=st.session_state.proxy_user,
            )
            st.session_state.proxy_pass = st.text_input(
                "Password (optional)",
                type="password",
                value=st.session_state.proxy_pass,
            )

    return proxy_config(st.session_state)


def _account_label(account: dict) -> str:
    if account["username"]:
        return f"@{account['username']}"

    full_name = (
        f"{account['first_name']} {account['last_name']}"
    ).strip()
    return full_name or str(account["telegram_user_id"])


def _restore_selected_account(
    settings,
    user: dict,
    account_id: int,
    proxy,
) -> None:
    account = get_account(
        settings.db_file,
        user["id"],
        account_id,
    )
    if not account:
        return

    try:
        with st.spinner("Connecting to Telegram…"):
            st.session_state.telegram_user = restore(
                settings,
                account["encrypted_session"],
                settings.session_encryption_key,
                proxy,
                peer_records=load_peer_records(
                    settings.db_file,
                    account_id,
                ),
            )
    except Exception as exc:
        st.sidebar.error(
            f"Failed to restore Telegram session: {exc}"
        )


def _render_connected_account_actions(
    settings,
    user: dict,
    account_id: int,
) -> None:
    telegram_user = st.session_state.telegram_user

    st.sidebar.markdown(
        badge_html("Connected", "success"),
        unsafe_allow_html=True,
    )

    full_name = (
        f"{telegram_user['first_name']} "
        f"{telegram_user['last_name']}"
    ).strip()
    if full_name:
        st.sidebar.caption(full_name)
    st.sidebar.caption(f"Telegram ID {telegram_user['id']}")

    refresh_col, add_col = st.sidebar.columns(2)
    with refresh_col:
        if st.button(
            "Refresh chats",
            key="sidebar-refresh-chats",
            use_container_width=True,
        ):
            st.session_state.dialogs = []
            st.session_state.force_refresh_dialogs = True
            st.rerun()

    with add_col:
        if st.button(
            "Add account",
            key="sidebar-add-account-connected",
            use_container_width=True,
        ):
            _start_login()
            st.rerun()

    with st.sidebar.expander(
        "Account actions",
        expanded=False,
    ):
        st.caption(
            "Disconnect keeps this account saved. "
            "Log out removes it from Telegram Harbor."
        )

        if st.button(
            "Disconnect",
            key="sidebar-disconnect-telegram",
            use_container_width=True,
        ):
            disconnect()
            st.session_state.telegram_user = None
            st.session_state.messages = []
            st.rerun()

        if st.button(
            "Log out & remove",
            key="sidebar-logout-telegram",
            use_container_width=True,
        ):
            try:
                logout()
            finally:
                delete_account(
                    settings.db_file,
                    user["id"],
                    account_id,
                )
                st.session_state.telegram_user = None
                st.session_state.selected_telegram_account_id = None
                st.session_state.selected_chat_id = None
                st.session_state.messages = []
                st.rerun()


def _render_account_selector(
    settings,
    user: dict,
    proxy,
) -> None:
    st.sidebar.markdown(
        section_title_html("Telegram account"),
        unsafe_allow_html=True,
    )

    accounts = list_accounts(
        settings.db_file,
        user["id"],
    )

    if not accounts:
        st.sidebar.caption(
            "No Telegram account has been added yet."
        )
        if st.sidebar.button(
            "Add Telegram account",
            key="sidebar-add-first-account",
            use_container_width=True,
        ):
            _start_login()
            st.rerun()
        return

    labels = {
        account["id"]: _account_label(account)
        for account in accounts
    }

    current = st.session_state.selected_telegram_account_id
    if current not in labels:
        current = next(iter(labels))
        st.session_state.selected_telegram_account_id = current

    selected = st.sidebar.selectbox(
        "Active account",
        list(labels),
        index=list(labels).index(current),
        format_func=lambda account_id: labels[account_id],
        label_visibility="collapsed",
    )

    if _apply_account_selection(
        st.session_state,
        selected,
    ):
        disconnect()
        st.rerun()

    account_id = st.session_state.selected_telegram_account_id

    if (
        account_id
        and not st.session_state.telegram_login_active
        and not st.session_state.telegram_user
    ):
        _restore_selected_account(
            settings,
            user,
            account_id,
            proxy,
        )

    if st.session_state.telegram_user:
        _render_connected_account_actions(
            settings,
            user,
            account_id,
        )
    else:
        st.sidebar.markdown(
            badge_html("Disconnected", "warning"),
            unsafe_allow_html=True,
        )
        if st.sidebar.button(
            "Add account",
            key="sidebar-add-account-disconnected",
            use_container_width=True,
        ):
            _start_login()
            st.rerun()


def _save_verified_account(
    settings,
    user: dict,
    telegram_user: dict,
) -> int:
    encrypted = encrypt_session(
        settings.session_encryption_key,
        export_session(),
    )
    return save_account(
        settings.db_file,
        user["id"],
        telegram_user,
        encrypted,
    )


def _render_telegram_login(settings, user: dict, proxy) -> None:
    if (
        not st.session_state.telegram_login_active
        or st.session_state.telegram_user
    ):
        return

    st.sidebar.markdown(
        section_title_html("Add Telegram account"),
        unsafe_allow_html=True,
    )

    stage = st.session_state.telegram_login_stage

    if stage == "phone":
        with st.sidebar.form("tg_phone"):
            phone = st.text_input(
                "Phone number",
                placeholder="+989123456789",
            )
            submitted = st.form_submit_button(
                "Send login code",
                use_container_width=True,
            )

        if submitted:
            try:
                code_hash = send_code(
                    settings,
                    phone.strip(),
                    proxy,
                )
                st.session_state.telegram_login_phone = phone.strip()
                st.session_state.telegram_phone_code_hash = code_hash
                st.session_state.telegram_login_stage = "code"
                st.rerun()
            except Exception as exc:
                st.sidebar.error(f"Failed to send code: {exc}")
        return

    if stage == "code":
        st.sidebar.info(
            f"Code sent to {st.session_state.telegram_login_phone}"
        )
        with st.sidebar.form("tg_code"):
            code = st.text_input("Telegram code")
            submitted = st.form_submit_button(
                "Verify code",
                use_container_width=True,
            )

        if submitted:
            try:
                status, telegram_user = verify_code(
                    st.session_state.telegram_login_phone,
                    st.session_state.telegram_phone_code_hash,
                    code.strip(),
                )
                if status == "2fa":
                    st.session_state.telegram_login_stage = "2fa"
                    st.rerun()
                else:
                    account_id = _save_verified_account(
                        settings,
                        user,
                        telegram_user,
                    )
                    st.session_state.telegram_user = telegram_user
                    st.session_state.selected_telegram_account_id = (
                        account_id
                    )
                    _reset_login()
                    st.rerun()
            except PhoneCodeExpired:
                st.sidebar.error(
                    "The Telegram code has expired. "
                    "Request a new code."
                )
            except PhoneCodeInvalid:
                st.sidebar.error(
                    "The Telegram code is invalid."
                )
            except PhoneNumberInvalid:
                st.sidebar.error(
                    "The Telegram phone number is invalid."
                )
            except Exception as exc:
                st.sidebar.error(
                    f"Code verification failed: {exc}"
                )

        action_col, change_col = st.sidebar.columns(2)

        with action_col:
            if st.button(
                "Resend code",
                key="sidebar-resend-code",
                use_container_width=True,
            ):
                try:
                    st.session_state.telegram_phone_code_hash = (
                        send_code(
                            settings,
                            st.session_state.telegram_login_phone,
                            proxy,
                        )
                    )
                    st.rerun()
                except Exception as exc:
                    st.sidebar.error(
                        f"Failed to resend code: {exc}"
                    )

        with change_col:
            if st.button(
                "Change phone",
                key="sidebar-change-phone",
                use_container_width=True,
            ):
                _reset_login()
                st.session_state.telegram_login_active = True
                st.rerun()
        return

    st.sidebar.info(
        "This account has Two-Step Verification enabled."
    )
    with st.sidebar.form("tg_2fa"):
        password = st.text_input(
            "Telegram 2FA password",
            type="password",
        )
        submitted = st.form_submit_button(
            "Login",
            use_container_width=True,
        )

    if submitted:
        try:
            telegram_user = verify_2fa(password)
            account_id = _save_verified_account(
                settings,
                user,
                telegram_user,
            )
            st.session_state.telegram_user = telegram_user
            st.session_state.selected_telegram_account_id = account_id
            _reset_login()
            st.rerun()
        except PasswordHashInvalid:
            st.sidebar.error(
                "The Telegram 2FA password is incorrect."
            )
        except Exception as exc:
            st.sidebar.error(f"2FA verification failed: {exc}")


def render_sidebar(settings) -> str:
    user = st.session_state.web_user

    _render_brand()
    _render_web_account(settings, user)
    st.sidebar.divider()

    st.sidebar.markdown(
        section_title_html("Workspace"),
        unsafe_allow_html=True,
    )
    workspace = st.sidebar.radio(
        "Workspace",
        ("Telegram Messages", "YouTube Download"),
        key="workspace",
        label_visibility="collapsed",
    )

    if workspace == "YouTube Download":
        st.sidebar.caption(
            "YouTube uses the host network directly. "
            "Telegram SOCKS5 proxy settings are not reused."
        )
        return workspace

    st.sidebar.divider()
    proxy = _render_network_settings()
    st.sidebar.divider()

    _render_account_selector(
        settings,
        user,
        proxy,
    )
    _render_telegram_login(
        settings,
        user,
        proxy,
    )

    return workspace
