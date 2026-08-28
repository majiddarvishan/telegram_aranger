from datetime import date, timedelta

import streamlit as st

from db.tags import all_tags, get_tags, save_tags
from services.telegram_service import delete_message, get_dialogs, history
from utils.date_range import bounds, normalize_range


def _chat_label(chat):
    prefix = {
        "private": "👤",
        "group": "👥",
        "supergroup": "👥",
        "channel": "📢",
    }.get(chat["type"], "💬")
    username = f" (@{chat['username']})" if chat.get("username") else ""
    return f"{prefix} {chat['title']}{username}"


def _set_pending_date_range(start_date, end_date):
    """Schedule a date-range change for the next Streamlit rerun."""
    st.session_state.pending_message_date_range = (start_date, end_date)


def _prepare_date_range_widget(today):
    """Apply pending navigation before the date widget is instantiated."""
    pending = st.session_state.pop("pending_message_date_range", None)
    if pending:
        st.session_state.message_date_range_picker = pending

    current = normalize_range(
        st.session_state.get("message_date_range_picker"),
        (today - timedelta(days=6), today),
    )

    start_date, end_date = current
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    st.session_state.message_date_range = (start_date, end_date)
    return start_date, end_date


def render_main(settings):
    if not st.session_state.telegram_user or not st.session_state.selected_telegram_account_id:
        st.title("📂 Telegram Saved Messages Manager")
        st.info("Add or select a Telegram account from the sidebar.")
        return

    st.title("📂 Telegram Message Manager")

    # -----------------------------------------------------
    # Load dialogs
    # -----------------------------------------------------
    if not st.session_state.dialogs:
        try:
            st.session_state.dialogs = get_dialogs()
        except Exception as exc:
            st.error(f"Failed to load chats: {exc}")
            return

    dialogs = st.session_state.dialogs
    if not dialogs:
        st.warning("No chats, groups, or channels were returned by Telegram.")
        return

    # Chat selection is intentionally kept on the main page.
    # It is also refreshed whenever the active Telegram account changes.
    options = {chat["id"]: _chat_label(chat) for chat in dialogs}
    current_chat_id = st.session_state.selected_chat_id

    if current_chat_id not in options:
        current_chat_id = next(iter(options))
        st.session_state.selected_chat_id = current_chat_id

    selected_chat_id = st.selectbox(
        "💬 Select Chat / Group / Channel",
        options=list(options),
        index=list(options).index(current_chat_id),
        format_func=lambda chat_id: options[chat_id],
        key="chat_selector",
    )

    if selected_chat_id != st.session_state.selected_chat_id:
        st.session_state.selected_chat_id = selected_chat_id
        st.session_state.messages = []
        st.rerun()

    # -----------------------------------------------------
    # Date range
    # -----------------------------------------------------
    today = date.today()
    start_date, end_date = _prepare_date_range_widget(today)

    picked = st.sidebar.date_input(
        "Message Date Range",
        value=(start_date, end_date),
        max_value=today,
        key="message_date_range_picker",
    )

    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start_date, end_date = picked
    else:
        start_date = end_date = picked

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    st.session_state.message_date_range = (start_date, end_date)
    st.sidebar.caption(f"Showing: {start_date.isoformat()} → {end_date.isoformat()}")

    # -----------------------------------------------------
    # Search / Tags
    # -----------------------------------------------------
    search = st.text_input("🔍 Search message text")

    tags = all_tags(settings.db_file, st.session_state.selected_telegram_account_id)
    tag = st.selectbox("🏷️ Tag", ["All"] + tags)

    # -----------------------------------------------------
    # Fetch messages
    # -----------------------------------------------------
    if (
        not st.session_state.messages
        or st.button("🔄 Refresh Messages")
    ):
        with st.spinner("Fetching messages..."):
            try:
                start_dt, end_dt = bounds(start_date, end_date)
                st.session_state.messages = history(
                    selected_chat_id,
                    start_dt,
                    end_dt,
                    settings.default_message_limit,
                )
            except Exception as exc:
                st.error(f"Failed to fetch messages: {exc}")
                st.session_state.messages = []

    # -----------------------------------------------------
    # Filter messages
    # -----------------------------------------------------
    messages = []
    account_id = st.session_state.selected_telegram_account_id

    for message in st.session_state.messages:
        message_date = message["date"].date()
        if not start_date <= message_date <= end_date:
            continue
        if search and search.lower() not in message["text"].lower():
            continue

        message_tags = get_tags(settings.db_file, account_id, message["id"])
        if tag != "All" and tag not in message_tags:
            continue

        messages.append((message, message_tags))

    st.caption(f"{len(messages)} message(s) in selected range")

    # -----------------------------------------------------
    # Message cards
    # -----------------------------------------------------
    for message, current_tags in messages:
        message_id = message["id"]

        with st.container(border=True):
            left, right = st.columns([4, 1])

            with left:
                st.write(message["text"])
                st.caption(
                    f"📅 {message['date'].strftime('%Y-%m-%d %H:%M:%S')} | "
                    f"ID: {message_id}"
                )

            with right:
                value = st.text_input(
                    "Tags",
                    ", ".join(current_tags),
                    key=f"tags_{account_id}_{selected_chat_id}_{message_id}",
                )

                if st.button(
                    "Save Tags",
                    key=f"save_{account_id}_{selected_chat_id}_{message_id}",
                ):
                    save_tags(settings.db_file, account_id, message_id, value.split(","))
                    st.rerun()

                if st.button(
                    "🗑️ Delete",
                    key=f"del_{account_id}_{selected_chat_id}_{message_id}",
                    type="primary",
                ):
                    try:
                        delete_message(selected_chat_id, message_id)
                        st.session_state.messages = [
                            item
                            for item in st.session_state.messages
                            if item["id"] != message_id
                        ]
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to delete message: {exc}")

    # -----------------------------------------------------
    # Fixed navigation bar
    # -----------------------------------------------------
    st.markdown(
        """
        <style>
        .message-nav {
            position: fixed;
            bottom: 18px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            width: min(720px, calc(100vw - 340px));
            background: var(--background-color);
            padding: 10px 16px;
            border-radius: 12px;
            border: 1px solid rgba(128,128,128,.35);
            box-shadow: 0 4px 18px rgba(0,0,0,.15);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="message-nav">', unsafe_allow_html=True)
    previous_col, date_col, next_col = st.columns([1, 2, 1])

    with previous_col:
        if st.button("◀ Previous Day", use_container_width=True):
            _set_pending_date_range(
                start_date - timedelta(days=1),
                end_date - timedelta(days=1),
            )
            st.rerun()

    with date_col:
        st.markdown(
            f"<div style='text-align:center;padding:7px 0'>"
            f"<b>{start_date.isoformat()} → {end_date.isoformat()}</b>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with next_col:
        if st.button("Next Day ▶", use_container_width=True):
            if end_date < today:
                new_end = min(end_date + timedelta(days=1), today)
                new_start = min(start_date + timedelta(days=1), new_end)
                _set_pending_date_range(new_start, new_end)
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
