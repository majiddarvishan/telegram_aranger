import asyncio
from datetime import date,timedelta
try: asyncio.get_event_loop()
except RuntimeError:
 loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
import streamlit as st
from pyrogram.errors import PhoneCodeExpired,PhoneCodeInvalid,PhoneNumberInvalid,PasswordHashInvalid
from database.connection import initialize_database
from services.auth_service import create_user,authenticate_user
from database.telegram_accounts import *
from database.tags import *
from runtime.telegram_runtime import get_runtime
from services.telegram_service import *
from ui.state import initialize_state


def get_proxy_config() -> dict | None:
    """Build the SOCKS5 proxy configuration from Streamlit state."""
    if not st.session_state.get("use_proxy", True):
        return None

    proxy = {
        "scheme": "socks5",
        "hostname": st.session_state.get("proxy_host", "127.0.0.1"),
        "port": int(st.session_state.get("proxy_port", 1080)),
    }

    username = st.session_state.get("proxy_user", "").strip()
    password = st.session_state.get("proxy_pass", "").strip()

    if username:
        proxy["username"] = username

    if password:
        proxy["password"] = password

    return proxy
initialize_database(); initialize_state()
# 21. Page Configuration
# =========================================================

st.set_page_config(
    page_title="Telegram Saved Messages Manager",
    layout="wide",
)


# =========================================================
# 22. Authentication UI
# =========================================================

def reset_telegram_login_state() -> None:
    """Reset the Telegram login flow and disconnect its temporary client."""

    runtime = get_runtime()

    if runtime.client is not None:
        try:
            runtime.run(runtime.client.disconnect())
        except Exception:
            pass
        runtime.client = None

    st.session_state.telegram_login_stage = "phone"
    st.session_state.telegram_login_active = False
    st.session_state.telegram_login_phone = ""
    st.session_state.telegram_phone_code_hash = ""


def start_telegram_login() -> None:
    """Start a new Telegram account login flow."""

    reset_telegram_login_state()
    st.session_state.telegram_login_active = True
    st.session_state.telegram_user = None
    st.session_state.messages = []


def render_authentication():

    st.title(
        "🔐 Telegram Saved Messages Manager"
    )

    st.info(
        "Please login to the Web Application."
    )

    login_tab, register_tab = st.tabs(
        [
            "Login",
            "Create Account",
        ]
    )

    with login_tab:

        with st.form(
            "web_login_form"
        ):

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            login = st.form_submit_button(
                "Login",
                use_container_width=True,
            )

        if login:

            user = authenticate_user(
                username,
                password,
            )

            if user:

                st.session_state.web_user = (
                    user
                )

                st.rerun()

            else:

                st.error(
                    "Invalid username or password."
                )

    with register_tab:

        with st.form(
            "web_register_form"
        ):

            display_name = st.text_input(
                "Display Name"
            )

            username = st.text_input(
                "Username"
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
            )

            register = st.form_submit_button(
                "Create Account",
                use_container_width=True,
            )

        if register:

            if not username.strip():

                st.error(
                    "Username is required."
                )

            elif len(password) < 8:

                st.error(
                    "Password must contain at least 8 characters."
                )

            elif password != confirm_password:

                st.error(
                    "Passwords do not match."
                )

            else:

                created = create_user(
                    username,
                    password,
                    display_name,
                )

                if created:

                    st.success(
                        "Account created. "
                        "You can now login."
                    )

                else:

                    st.error(
                        "Username already exists."
                    )


if st.session_state.web_user is None:

    render_authentication()

    st.stop()


# =========================================================
# 23. Sidebar - Web User
# =========================================================

web_user = st.session_state.web_user

st.sidebar.title(
    "👤 Account"
)

st.sidebar.write(
    f"**{web_user['display_name']}**"
)

st.sidebar.caption(
    f"@{web_user['username']}"
)


if st.sidebar.button(
    "🚪 Logout Web Application",
    use_container_width=True,
):

    runtime = st.session_state.get(
        "telegram_runtime"
    )

    if runtime:

        try:

            runtime.stop()

        except Exception:
            pass

    st.session_state.clear()

    st.rerun()


st.sidebar.markdown("---")


# =========================================================
# 24. Sidebar - Proxy
# =========================================================

st.sidebar.header(
    "⚙️ Network Settings"
)

st.session_state.use_proxy = (
    st.sidebar.checkbox(
        "Enable SOCKS5 Proxy",
        value=st.session_state.use_proxy,
    )
)

if st.session_state.use_proxy:

    st.session_state.proxy_host = (
        st.sidebar.text_input(
            "Proxy Host/IP",
            value=st.session_state.proxy_host,
        )
    )

    st.session_state.proxy_port = (
        st.sidebar.number_input(
            "Proxy Port",
            value=st.session_state.proxy_port,
            min_value=1,
            max_value=65535,
        )
    )

    st.session_state.proxy_user = (
        st.sidebar.text_input(
            "Username (Optional)",
            value=st.session_state.proxy_user,
        )
    )

    st.session_state.proxy_pass = (
        st.sidebar.text_input(
            "Password (Optional)",
            type="password",
            value=st.session_state.proxy_pass,
        )
    )


proxy_config = get_proxy_config()


# =========================================================
# 25. Telegram Accounts
# =========================================================

st.sidebar.markdown("---")

st.sidebar.header(
    "📱 Telegram Accounts"
)

telegram_accounts = get_telegram_accounts(
    web_user["id"]
)


# =========================================================
# 26. Add Telegram Account
# =========================================================

if st.sidebar.button(
    "➕ Add Telegram Account",
    use_container_width=True,
):
    start_telegram_login()
    st.rerun()


# =========================================================
# 27. Account Selector
# =========================================================

if telegram_accounts:

    account_options = {}

    for account in telegram_accounts:

        username = account["username"]

        if username:

            label = (
                f"@{username} "
                f"({account['telegram_user_id']})"
            )

        else:

            name = (
                f"{account['first_name']} "
                f"{account['last_name']}"
            ).strip()

            label = (
                f"{name or account['telegram_user_id']}"
            )

        account_options[
            account["id"]
        ] = label

    current_account_id = (
        st.session_state.selected_telegram_account_id
    )

    if (
        current_account_id
        not in account_options
    ):

        current_account_id = (
            next(
                iter(account_options)
            )
        )

        st.session_state.selected_telegram_account_id = (
            current_account_id
        )

    selected_account_id = (
        st.sidebar.selectbox(
            "Active Telegram Account",
            options=list(
                account_options.keys()
            ),
            index=list(
                account_options.keys()
            ).index(
                current_account_id
            ),
            format_func=lambda x:
                account_options[x],
        )
    )

    if (
        selected_account_id
        != st.session_state.selected_telegram_account_id
    ):

        st.session_state.selected_telegram_account_id = (
            selected_account_id
        )

        st.session_state.messages = []

        runtime = get_runtime()

        if runtime.client:

            try:
                runtime.run(
                    runtime.client.disconnect()
                )
            except Exception:
                pass

            runtime.client = None

        st.rerun()


# =========================================================
# 27. Connect Selected Telegram Account
# =========================================================

selected_account_id = (
    st.session_state.selected_telegram_account_id
)

if selected_account_id:

    selected_account = get_telegram_account(
        web_user["id"],
        selected_account_id,
    )

    runtime = get_runtime()

    if (
        selected_account
        and runtime.client is None
        and not st.session_state.telegram_login_active
    ):

        try:

            with st.spinner(
                "Connecting to Telegram..."
            ):

                telegram_user = (
                    restore_telegram_account(
                        selected_account,
                        proxy_config,
                    )
                )

            st.session_state.telegram_user = (
                telegram_user
            )

        except Exception as e:

            st.error(
                f"Failed to restore Telegram session: {e}"
            )

            st.session_state.telegram_user = None


# =========================================================
# 29. Connected Telegram Account
# =========================================================

if st.session_state.telegram_user:

    telegram_user = (
        st.session_state.telegram_user
    )

    st.sidebar.success(
        "🟢 Telegram Connected"
    )

    name = (
        f"{telegram_user['first_name']} "
        f"{telegram_user['last_name']}"
    ).strip()

    if name:

        st.sidebar.caption(
            f"👤 {name}"
        )

    if telegram_user["username"]:

        st.sidebar.caption(
            f"@{telegram_user['username']}"
        )

    st.sidebar.caption(
        f"ID: {telegram_user['id']}"
    )

    if st.sidebar.button(
        "🔌 Disconnect Telegram",
        use_container_width=True,
    ):
        try:
            with st.spinner("Disconnecting Telegram..."):
                disconnect_telegram()

            st.session_state.telegram_user = None
            st.session_state.messages = []
            st.rerun()

        except Exception as e:
            st.sidebar.error(
                f"Failed to disconnect Telegram: {e}"
            )

    if st.sidebar.button(
        "🚪 Logout Telegram Account",
        use_container_width=True,
    ):
        try:
            with st.spinner("Logging out from Telegram..."):
                logout_telegram()

            delete_telegram_account(
                web_user["id"],
                selected_account_id,
            )

            st.session_state.telegram_user = None
            st.session_state.selected_telegram_account_id = None
            st.session_state.messages = []
            st.rerun()

        except Exception as e:
            st.sidebar.error(
                f"Failed to logout Telegram: {e}"
            )

# =========================================================
# 30. Telegram Login UI
# =========================================================

if (
    not st.session_state.telegram_user
    and st.session_state.telegram_login_active
):

    st.sidebar.markdown("---")

    st.sidebar.header(
        "🔐 Add Telegram Account"
    )

    stage = (
        st.session_state.telegram_login_stage
    )

    # -----------------------------------------------------
    # Phone
    # -----------------------------------------------------

    if stage == "phone":

        with st.sidebar.form(
            "telegram_phone_form"
        ):

            phone = st.text_input(
                "Phone Number",
                placeholder="+989123456789",
            )

            send_code = st.form_submit_button(
                "📱 Send Login Code",
                use_container_width=True,
            )

        if send_code:

            phone = phone.strip()

            if not phone:

                st.sidebar.error(
                    "Phone number is required."
                )

            else:

                try:

                    with st.spinner(
                        "Sending Telegram code..."
                    ):

                        phone_code_hash = (
                            send_login_code(
                                phone,
                                proxy_config,
                            )
                        )

                    st.session_state.telegram_login_phone = (
                        phone
                    )

                    st.session_state.telegram_phone_code_hash = (
                        phone_code_hash
                    )

                    st.session_state.telegram_login_active = True
                    st.session_state.telegram_login_stage = "code"

                    st.rerun()

                except Exception as e:

                    st.sidebar.error(
                        f"Failed to send code: {e}"
                    )

    # -----------------------------------------------------
    # Code
    # -----------------------------------------------------

    elif stage == "code":

        st.sidebar.info(
            f"Code sent to "
            f"{st.session_state.telegram_login_phone}"
        )

        with st.sidebar.form(
            "telegram_code_form"
        ):

            code = st.text_input(
                "Telegram Code",
                placeholder="12345",
            )

            verify = st.form_submit_button(
                "✅ Verify Code",
                use_container_width=True,
            )

        if verify:

            code = code.strip()

            if not code:

                st.sidebar.error(
                    "Enter the Telegram code."
                )

            else:

                try:

                    status, telegram_user = (
                        verify_login_code(
                            st.session_state.telegram_login_phone,
                            st.session_state.telegram_phone_code_hash,
                            code,
                        )
                    )

                    if status == "2fa":

                        st.session_state.telegram_login_stage = (
                            "2fa"
                        )

                        st.rerun()

                    else:

                        session_string = (
                            export_current_session()
                        )

                        account_id = (
                            save_telegram_account(
                                web_user["id"],
                                telegram_user,
                                session_string,
                            )
                        )

                        st.session_state.telegram_user = (
                            telegram_user
                        )

                        st.session_state.selected_telegram_account_id = (
                            account_id
                        )

                        st.session_state.telegram_login_stage = "phone"
                        st.session_state.telegram_login_active = False

                        st.session_state.telegram_login_phone = (
                            ""
                        )

                        st.session_state.telegram_phone_code_hash = (
                            ""
                        )

                        st.session_state.messages = []

                        st.rerun()

                except PhoneCodeExpired:

                    st.sidebar.error(
                        "The Telegram code has expired. "
                        "Please request a new code."
                    )

                except PhoneCodeInvalid:

                    st.sidebar.error(
                        "The Telegram code is invalid."
                    )

                except PhoneNumberInvalid:

                    st.sidebar.error(
                        "The Telegram phone number is invalid."
                    )

                except Exception as e:

                    st.sidebar.error(
                        f"Code verification failed: {e}"
                    )

        if st.sidebar.button(
            "🔄 Resend Code",
            use_container_width=True,
        ):

            try:

                with st.spinner(
                    "Sending a new code..."
                ):

                    phone_code_hash = (
                        send_login_code(
                            st.session_state.telegram_login_phone,
                            proxy_config,
                        )
                    )

                st.session_state.telegram_phone_code_hash = (
                    phone_code_hash
                )

                st.sidebar.success(
                    "A new Telegram code was sent."
                )

                st.rerun()

            except Exception as e:

                st.sidebar.error(
                    f"Failed to resend code: {e}"
                )

        if st.sidebar.button(
            "↩️ Change Phone Number",
            use_container_width=True,
        ):

            runtime = get_runtime()

            if runtime.client:

                try:

                    runtime.run(
                        runtime.client.disconnect()
                    )

                except Exception:
                    pass

                runtime.client = None

            st.session_state.telegram_login_stage = (
                "phone"
            )

            st.session_state.telegram_login_phone = (
                ""
            )

            st.session_state.telegram_phone_code_hash = (
                ""
            )

            st.rerun()

    # -----------------------------------------------------
    # 2FA
    # -----------------------------------------------------

    elif stage == "2fa":

        st.sidebar.info(
            "This Telegram account has "
            "Two-Step Verification enabled."
        )

        with st.sidebar.form(
            "telegram_2fa_form"
        ):

            password = st.text_input(
                "Telegram 2FA Password",
                type="password",
            )

            login_2fa = st.form_submit_button(
                "🔓 Login",
                use_container_width=True,
            )

        if login_2fa:

            if not password:

                st.sidebar.error(
                    "Enter your Telegram 2FA password."
                )

            else:

                try:

                    telegram_user = (
                        verify_2fa(
                            password
                        )
                    )

                    session_string = (
                        export_current_session()
                    )

                    account_id = (
                        save_telegram_account(
                            web_user["id"],
                            telegram_user,
                            session_string,
                        )
                    )

                    st.session_state.telegram_user = (
                        telegram_user
                    )

                    st.session_state.selected_telegram_account_id = (
                        account_id
                    )

                    st.session_state.telegram_login_stage = "phone"
                    st.session_state.telegram_login_active = False

                    st.session_state.telegram_login_phone = (
                        ""
                    )

                    st.session_state.telegram_phone_code_hash = (
                        ""
                    )

                    st.session_state.messages = []

                    st.rerun()

                except PasswordHashInvalid:

                    st.sidebar.error(
                        "The Telegram 2FA password is incorrect."
                    )

                except Exception as e:

                    st.sidebar.error(
                        f"2FA verification failed: {e}"
                    )

        if st.sidebar.button(
            "↩️ Start Over",
            use_container_width=True,
        ):

            runtime = get_runtime()

            if runtime.client:

                try:

                    runtime.run(
                        runtime.client.disconnect()
                    )

                except Exception:
                    pass

                runtime.client = None

            st.session_state.telegram_login_stage = (
                "phone"
            )

            st.session_state.telegram_login_phone = (
                ""
            )

            st.session_state.telegram_phone_code_hash = (
                ""
            )

            st.rerun()


# =========================================================
# 30. Stop if Telegram is Not Connected
# =========================================================

if (
    not st.session_state.telegram_user
    or not st.session_state.selected_telegram_account_id
):

    st.info(
        "📱 Add or select a Telegram account "
        "from the sidebar."
    )

    st.stop()


# =========================================================
# 31. Active Account
# =========================================================

account_id = (
    st.session_state.selected_telegram_account_id
)


# =========================================================
# 32. Message Date Range
# =========================================================
from datetime import date, timedelta

st.sidebar.markdown("---")
st.sidebar.header("📅 Message Date Range")

today = date.today()
default_start = today - timedelta(days=6)

def _normalize_range(value):
    if isinstance(value, (tuple, list)) and len(value) == 2:
        first, second = value
        if isinstance(first, date) and isinstance(second, date):
            return first, second
    if isinstance(value, date):
        return value, value
    return default_start, today

stored_range = _normalize_range(
    st.session_state.get("message_date_range", (default_start, today))
)

# Keep the widget state and application state separate. Streamlit does not
# allow modifying a widget's keyed session-state value after the widget is
# instantiated during the same script run.
if "message_date_range_picker" not in st.session_state:
    st.session_state.message_date_range_picker = list(stored_range)

selected_range = st.sidebar.date_input(
    "Select date range",
    value=st.session_state.message_date_range_picker,
    max_value=today,
    key="message_date_range_picker",
)

start_date, end_date = _normalize_range(selected_range)

if start_date > end_date:
    start_date, end_date = end_date, start_date

st.session_state.message_date_range = (start_date, end_date)

st.sidebar.caption(
    f"Showing: {start_date.isoformat()} → {end_date.isoformat()}"
)

# =========================================================
# 33. Date Navigation
# =========================================================
def shift_message_range(days: int):
    """Shift the current date range by the requested number of days."""
    current_start, current_end = _normalize_range(
        st.session_state.get("message_date_range", (default_start, today))
    )

    delta = timedelta(days=days)
    new_start = current_start + delta
    new_end = current_end + delta

    # Do not allow navigation into the future.
    if new_end > today:
        new_end = today
        duration = current_end - current_start
        new_start = new_end - duration

    st.session_state.message_date_range = (new_start, new_end)
    st.session_state.message_date_range_picker = [new_start, new_end]
    st.session_state.messages = []


def go_previous_range():
    shift_message_range(-1)


def go_next_range():
    shift_message_range(1)

# The controls are rendered at the bottom of the main content. CSS makes
# this dedicated navigation bar fixed to the viewport instead of scrolling
# with the message list.
st.markdown(
    """
    <style>
    .message-navigation-spacer {
        height: 90px;
    }

    div[data-testid="stHorizontalBlock"]:has(.message-navigation-marker) {
        position: fixed;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 999999;
        padding: 12px 24px;
        background: rgba(255, 255, 255, 0.97);
        border-top: 1px solid rgba(128, 128, 128, 0.35);
        box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.08);
    }

    @media (prefers-color-scheme: dark) {
        div[data-testid="stHorizontalBlock"]:has(.message-navigation-marker) {
            background: rgba(14, 17, 23, 0.97);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Marker is placed in the first column so CSS can identify this specific
# horizontal block without affecting other column layouts in the page.
nav_col_prev, nav_col_date, nav_col_next = st.columns([1, 2, 1])

with nav_col_prev:
    st.markdown('<span class="message-navigation-marker"></span>', unsafe_allow_html=True)
    previous_clicked = st.button(
        "◀ Previous",
        use_container_width=True,
        on_click=go_previous_range,
    )

with nav_col_date:
    if start_date == end_date:
        navigation_label = start_date.isoformat()
    else:
        navigation_label = f"{start_date.isoformat()} → {end_date.isoformat()}"

    st.markdown(
        f"<div style='text-align:center;padding-top:8px;font-weight:600;'>{navigation_label}</div>",
        unsafe_allow_html=True,
    )

with nav_col_next:
    next_disabled = end_date >= today
    st.button(
        "Next ▶",
        use_container_width=True,
        disabled=next_disabled,
        on_click=go_next_range,
    )

st.markdown('<div class="message-navigation-spacer"></div>', unsafe_allow_html=True)

# =========================================================
# 34. Fetch Messages for Selected Range
# =========================================================
if (
    not st.session_state.messages
    or st.sidebar.button(
        "🔄 Refresh Selected Range",
        use_container_width=True,
    )
):
    with st.spinner("Fetching Saved Messages..."):
        try:
            st.session_state.messages = fetch_saved_messages_for_range(
                start_date,
                end_date,
            )
        except Exception as e:
            st.error(f"Failed to fetch messages: {e}")
            st.session_state.messages = []

# 34. Tags Filter
# =========================================================

all_tags = get_all_tags(
    account_id
)

selected_tag = st.sidebar.selectbox(
    "Filter by Tag:",
    ["All"] + all_tags,
)


# =========================================================
# 35. Search
# =========================================================

search_query = st.text_input(
    "🔍 Search message text:"
)


# =========================================================
# 36. Render Messages
# =========================================================

for message in st.session_state.messages:

    message_id = message["id"]

    text = message["text"]

    current_tags = get_tags(
        account_id,
        message_id,
    )

    if (
        selected_tag != "All"
        and selected_tag not in current_tags
    ):
        continue

    if (
        search_query
        and search_query.lower()
        not in text.lower()
    ):
        continue

    with st.container():

        st.markdown("---")

        col_content, col_actions = (
            st.columns([3, 1])
        )

        # -------------------------------------------------
        # Content
        # -------------------------------------------------

        with col_content:

            st.write(text)

            st.caption(
                f"📅 {message['date']} | "
                f"ID: {message_id}"
            )

            tg_link = (
                f"https://t.me/c/"
                f"{message['user_id']}/"
                f"{message_id}"
            )

            st.markdown(
                "[🔗 Open in Telegram]"
                f"({tg_link})"
            )

        # -------------------------------------------------
        # Actions
        # -------------------------------------------------

        with col_actions:

            tags_input = st.text_input(
                "Tags (comma separated):",
                value=", ".join(
                    current_tags
                ),
                key=(
                    f"tags_"
                    f"{account_id}_"
                    f"{message_id}"
                ),
            )

            if st.button(
                "Save Tags",
                key=(
                    f"save_"
                    f"{account_id}_"
                    f"{message_id}"
                ),
            ):

                save_tags(
                    account_id,
                    message_id,
                    tags_input.split(","),
                )

                st.success(
                    "Tags updated."
                )

                st.rerun()

            if st.button(
                "🗑️ Delete Message",
                key=(
                    f"delete_"
                    f"{account_id}_"
                    f"{message_id}"
                ),
                type="primary",
            ):

                try:

                    delete_message(
                        message_id
                    )

                    st.session_state.messages = [
                        item
                        for item
                        in st.session_state.messages
                        if item["id"] != message_id
                    ]

                    st.success(
                        "Message deleted."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        f"Failed to delete message: {e}"
                    )