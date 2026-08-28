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
    """Schedule a date-range change before the date widget is created."""
    st.session_state.pending_message_date_range = (start_date, end_date)


def _prepare_date_range(today):
    """Prepare the date picker value before Streamlit creates the widget."""
    pending = st.session_state.pop("pending_message_date_range", None)
    if pending is not None:
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


def _render_header_styles():
    st.markdown(
        """
        <style>
        .st-key-message-header {
            position: fixed;
            top: 0;
            left: max(0px, var(--sidebar-width, 21rem));
            right: 0;
            z-index: 10000;
            padding: 10px 24px 12px 24px;
            background: var(--background-color);
            border-bottom: 1px solid rgba(128, 128, 128, 0.28);
            box-shadow: 0 3px 14px rgba(0, 0, 0, 0.10);
        }
        .st-key-message-header [data-testid="stHorizontalBlock"] {
            align-items: end;
            gap: 10px;
        }
        .st-key-message-header label {
            margin-bottom: 4px;
        }
        .st-key-message-header [data-testid="stDateInput"] {
            width: 100%;
        }
        .st-key-message-header [data-testid="stDateInput"] > div {
            width: 100%;
        }
        .message-header-spacer {
            height: 126px;
        }
        .st-key-message-navigation {
            position: fixed;
            bottom: 18px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            width: min(300px, calc(100vw - 48px));
            padding: 8px 12px;
            background: var(--background-color);
            border: 1px solid rgba(128, 128, 128, 0.35);
            border-radius: 12px;
            box-shadow: 0 4px 18px rgba(0, 0, 0, 0.15);
        }
        .st-key-message-navigation button {
            min-height: 38px;
            font-size: 20px;
        }
        .message-bottom-spacer {
            height: 82px;
        }
        @media (max-width: 900px) {
            .st-key-message-header {
                left: 0;
                padding-left: 12px;
                padding-right: 12px;
            }
            .message-header-spacer {
                height: 190px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_message_header(settings, options, current_chat_id, today):
    _render_header_styles()

    account_id = st.session_state.selected_telegram_account_id
    tags = all_tags(settings.db_file, account_id)
    start_date, end_date = _prepare_date_range(today)

    with st.container(key="message_header"):
        chat_col, search_col, tag_col = st.columns([2.7, 2.2, 1.2])

        with chat_col:
            selected_chat_id = st.selectbox(
                "💬 Chat / Group / Channel",
                options=list(options),
                index=list(options).index(current_chat_id),
                format_func=lambda chat_id: options[chat_id],
                key="chat_selector",
            )

        with search_col:
            search = st.text_input(
                "🔍 Search message text",
                key="message_search",
            )

        with tag_col:
            tag = st.selectbox(
                "🏷️ Tag",
                ["All"] + tags,
                key="message_tag_filter",
            )

        picked = st.date_input(
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

    st.markdown(
        '<div class="message-header-spacer"></div>',
        unsafe_allow_html=True,
    )

    return selected_chat_id, search, tag, start_date, end_date


def _fetch_messages_if_needed(settings, selected_chat_id, start_date, end_date):
    signature = (
        selected_chat_id,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    refresh = st.button("🔄 Refresh Messages")
    should_fetch = (
        not st.session_state.messages
        or st.session_state.get("message_query_signature") != signature
        or refresh
    )

    if not should_fetch:
        return

    with st.spinner("Fetching messages..."):
        try:
            start_dt, end_dt = bounds(start_date, end_date)
            st.session_state.messages = history(
                selected_chat_id,
                start_dt,
                end_dt,
                settings.default_message_limit,
            )
            st.session_state.message_query_signature = signature
        except Exception as exc:
            st.error(f"Failed to fetch messages: {exc}")
            st.session_state.messages = []
            st.session_state.message_query_signature = signature


def _render_navigation(start_date, end_date, today):
    st.markdown('<div class="message-bottom-spacer"></div>', unsafe_allow_html=True)

    with st.container(key="message_navigation"):
        previous_col, next_col = st.columns(2)

        with previous_col:
            if st.button(
                "◀",
                help="Previous Day",
                use_container_width=True,
                key="previous_day",
            ):
                _set_pending_date_range(
                    start_date - timedelta(days=1),
                    end_date - timedelta(days=1),
                )
                st.rerun()

        with next_col:
            if st.button(
                "▶",
                help="Next Day",
                use_container_width=True,
                key="next_day",
                disabled=end_date >= today,
            ):
                new_end = min(end_date + timedelta(days=1), today)
                new_start = min(start_date + timedelta(days=1), new_end)
                _set_pending_date_range(new_start, new_end)
                st.rerun()


def render_main(settings):
    if (
        not st.session_state.telegram_user
        or not st.session_state.selected_telegram_account_id
    ):
        st.info("Add or select a Telegram account from the sidebar.")
        return

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

    options = {chat["id"]: _chat_label(chat) for chat in dialogs}
    current_chat_id = st.session_state.selected_chat_id

    if current_chat_id not in options:
        current_chat_id = next(iter(options))
        st.session_state.selected_chat_id = current_chat_id

    today = date.today()
    selected_chat_id, search, tag, start_date, end_date = _render_message_header(
        settings,
        options,
        current_chat_id,
        today,
    )

    if selected_chat_id != st.session_state.selected_chat_id:
        st.session_state.selected_chat_id = selected_chat_id
        st.session_state.messages = []
        st.session_state.message_query_signature = None
        st.rerun()

    _fetch_messages_if_needed(
        settings,
        selected_chat_id,
        start_date,
        end_date,
    )

    account_id = st.session_state.selected_telegram_account_id
    messages = []

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

    _render_navigation(start_date, end_date, today)
