from datetime import date, timedelta
from pathlib import Path
import threading
import time

import streamlit as st

from db.dialogs import load_dialogs as load_cached_dialogs, replace_dialogs
from db.tags import all_tags, get_tags_for_messages, save_tags
from services.telegram_service import delete_message, get_dialogs, history, start_media_download
from ui.theme import MESSAGE_HEADER_CSS
from utils.date_range import bounds, normalize_range


_DIALOG_REFRESH_LOCK = threading.Lock()


def _format_bytes(size: int | None) -> str:
    if not size:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _media_state_key(account_id: int, chat_id: int, message_id: int, purpose: str) -> str:
    return f"{account_id}:{chat_id}:{message_id}:{purpose}"


def _delete_state_key(account_id: int, chat_id: int, message_id: int) -> str:
    return f"{account_id}:{chat_id}:{message_id}"


def _get_prepared_media(key: str):
    result = st.session_state.media_files.get(key)
    if not result:
        return None
    path = Path(result.get("path", ""))
    if not path.is_file():
        st.session_state.media_files.pop(key, None)
        return None
    return result


def _prepare_media(
    settings,
    account_id: int,
    chat_id: int,
    message_id: int,
    purpose: str,
    max_megabytes: int,
    force_download: bool = False,
):
    key = _media_state_key(account_id, chat_id, message_id, purpose)
    existing = _get_prepared_media(key)
    if existing:
        return existing

    progress_bar = st.progress(
        0,
        text="Downloading media from Telegram... 0%",
    )

    try:
        future, progress = start_media_download(
            chat_id=chat_id,
            message_id=message_id,
            account_id=account_id,
            settings=settings,
            max_megabytes=max_megabytes,
            force_download=force_download,
        )

        last_percent = -1
        while not future.done():
            current, total = progress.snapshot()
            percent = int((current * 100) / total) if total else 0
            percent = max(0, min(percent, 100))

            if percent != last_percent:
                size_text = ""
                if total:
                    size_text = f" · {_format_bytes(current)} / {_format_bytes(total)}"
                progress_bar.progress(
                    percent,
                    text=f"Downloading media from Telegram... {percent}%{size_text}",
                )
                last_percent = percent

            time.sleep(0.1)

        result = future.result()
        progress_bar.progress(
            100,
            text="Downloading media from Telegram... 100%",
        )
    except Exception as exc:
        progress_bar.empty()
        st.error(f"Failed to download media: {exc}")
        return None

    progress_bar.empty()
    st.session_state.media_files[key] = result
    return result


def _render_media(settings, account_id: int, message: dict) -> None:
    media = message.get("media")
    if not media:
        return

    media_type = media.get("type", "media")
    details = [media_type.replace("_", " ").title()]
    if media.get("file_size"):
        details.append(_format_bytes(media["file_size"]))
    if media.get("duration"):
        details.append(f"{media['duration']}s")
    if media.get("mime_type"):
        details.append(media["mime_type"])
    st.caption(" · ".join(details))

    chat_id = message["chat_id"]
    message_id = message["id"]

    if media_type == "photo":
        key = _media_state_key(account_id, chat_id, message_id, "preview")
        prepared = _get_prepared_media(key)
        if prepared is None and st.button(
            "🖼️ Show Photo",
            key=f"media_photo_{account_id}_{chat_id}_{message_id}",
        ):
            prepared = _prepare_media(
                settings,
                account_id,
                chat_id,
                message_id,
                "preview",
                settings.media_preview_max_mb,
            )
        if prepared:
            st.image(prepared["path"])
        return

    if media_type in ("video", "video_note", "animation"):
        play_key = _media_state_key(account_id, chat_id, message_id, "preview")
        prepared = _get_prepared_media(play_key)

        if prepared is None and st.button(
            "▶️ Load Video",
            key=f"media_play_{account_id}_{chat_id}_{message_id}",
        ):
            prepared = _prepare_media(
                settings,
                account_id,
                chat_id,
                message_id,
                "preview",
                settings.media_preview_max_mb,
            )

        if prepared:
            st.video(prepared["path"])

        if media_type == "video":
            download_key = _media_state_key(account_id, chat_id, message_id, "download")
            download_ready = _get_prepared_media(download_key) or prepared

            if download_ready is None and st.button(
                "⬇️ Prepare Video Download",
                key=f"media_prepare_download_{account_id}_{chat_id}_{message_id}",
            ):
                download_ready = _prepare_media(
                    settings,
                    account_id,
                    chat_id,
                    message_id,
                    "download",
                    settings.media_download_max_mb,
                )

            if download_ready:
                path = Path(download_ready["path"])
                try:
                    with path.open("rb") as file_handle:
                        st.download_button(
                            "⬇️ Download Video",
                            data=file_handle,
                            file_name=download_ready["file_name"],
                            mime=download_ready["mime_type"],
                            key=f"media_download_{account_id}_{chat_id}_{message_id}",
                            use_container_width=True,
                        )
                except OSError as exc:
                    st.error(f"Failed to open cached video: {exc}")

                if st.button(
                    "🔁 Redownload Video",
                    key=f"media_redownload_{account_id}_{chat_id}_{message_id}",
                    help="Discard the cached copy and download the video again from Telegram.",
                    use_container_width=True,
                ):
                    st.session_state.media_files.pop(download_key, None)
                    st.session_state.media_files.pop(play_key, None)
                    download_ready = _prepare_media(
                        settings,
                        account_id,
                        chat_id,
                        message_id,
                        "download",
                        settings.media_download_max_mb,
                        force_download=True,
                    )
                    if download_ready:
                        st.rerun()
        return

    st.info(f"{media_type.replace('_', ' ').title()} media is detected. Preview is not implemented yet.")


def _load_or_refresh_dialogs(
    settings,
    account_id: int,
    force_refresh: bool = False,
) -> tuple[list[dict], str | None]:
    cached = load_cached_dialogs(settings.db_file, account_id)
    if cached and not force_refresh:
        return cached, None

    with _DIALOG_REFRESH_LOCK:
        if not force_refresh:
            cached = load_cached_dialogs(settings.db_file, account_id)
            if cached:
                return cached, None

        try:
            dialogs = get_dialogs(settings.telegram_dialog_limit)
        except Exception as exc:
            if cached:
                return (
                    cached,
                    "Telegram chat refresh failed; showing cached chats. "
                    f"{exc}",
                )
            raise

        if dialogs:
            replace_dialogs(settings.db_file, account_id, dialogs)
        return dialogs, None


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


MESSAGE_HEADER_KEY = "message-header"
MESSAGE_SCROLL_KEY = "message-scroll-area"

def _render_message_header(settings, options, current_chat_id, today):
    account_id = st.session_state.selected_telegram_account_id
    tags = all_tags(settings.db_file, account_id)
    start_date, end_date = _prepare_date_range(today)

    with st.container(key=MESSAGE_HEADER_KEY):
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

        date_col, previous_col, next_col = st.columns([8.0, 1.0, 1.0])

        with date_col:
            picked = st.date_input(
                "Message Date Range",
                value=(start_date, end_date),
                max_value=today,
                key="message_date_range_picker",
            )

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

    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start_date, end_date = picked
    else:
        start_date = end_date = picked

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    st.session_state.message_date_range = (start_date, end_date)

    return selected_chat_id, search, tag, start_date, end_date


def _fetch_messages_if_needed(settings, selected_chat_id, start_date, end_date):
    range_signature = (
        selected_chat_id,
        start_date.isoformat(),
        end_date.isoformat(),
    )
    if st.session_state.get("message_range_signature") != range_signature:
        st.session_state.message_range_signature = range_signature
        st.session_state.message_result_limit = settings.default_message_limit
        st.session_state.message_query_signature = None
        st.session_state.messages = []

    result_limit = (
        st.session_state.get("message_result_limit")
        or settings.default_message_limit
    )
    signature = (*range_signature, result_limit)

    should_fetch = (
        not st.session_state.messages
        or st.session_state.get("message_query_signature") != signature
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
                result_limit,
            )
            st.session_state.message_query_signature = signature
        except Exception as exc:
            st.error(f"Failed to fetch messages: {exc}")
            st.session_state.messages = []
            st.session_state.message_query_signature = signature


def _render_message_actions(settings) -> None:
    loaded_count = len(st.session_state.messages)
    result_limit = (
        st.session_state.get("message_result_limit")
        or settings.default_message_limit
    )

    refresh_col, load_more_col, spacer_col = st.columns([1.2, 1.6, 6.2])

    with refresh_col:
        if st.button(
            "🔄 Refresh Messages",
            key="refresh_messages",
            use_container_width=True,
        ):
            st.session_state.message_query_signature = None
            st.rerun()

    with load_more_col:
        if loaded_count >= result_limit:
            if st.button(
                "➕ Load More Messages",
                key="load_more_messages",
                use_container_width=True,
            ):
                st.session_state.message_result_limit = (
                    result_limit + settings.default_message_limit
                )
                st.session_state.message_query_signature = None
                st.rerun()


def _message_matches_filters(
    message: dict,
    message_tags: list[str],
    start_date,
    end_date,
    search: str,
    tag: str,
) -> bool:
    message_date = message["date"].date()
    if not start_date <= message_date <= end_date:
        return False
    if search and search.lower() not in message["text"].lower():
        return False
    if tag != "All" and tag not in message_tags:
        return False
    return True


def _remove_message_from_state(
    messages: list[dict],
    media_files: dict,
    account_id: int,
    chat_id: int,
    message_id: int,
) -> tuple[list[dict], dict]:
    remaining = [
        item
        for item in messages
        if item["id"] != message_id
    ]
    prefix = f"{account_id}:{chat_id}:{message_id}:"
    cleaned_media = {
        key: value
        for key, value in media_files.items()
        if not key.startswith(prefix)
    }
    return remaining, cleaned_media


def _render_message_scroll_area(
    settings,
    account_id,
    selected_chat_id,
    messages,
):
    loaded_count = len(st.session_state.messages)
    result_limit = (
        st.session_state.get("message_result_limit")
        or settings.default_message_limit
    )

    with st.container(
        height=settings.message_scroll_height,
        border=True,
        key=MESSAGE_SCROLL_KEY,
    ):
        if loaded_count >= result_limit:
            st.caption(
                f"{len(messages)} visible message(s) · "
                f"{loaded_count} loaded · current limit {result_limit}"
            )
        else:
            st.caption(
                f"{len(messages)} visible message(s) · "
                f"{loaded_count} loaded · end of selected range"
            )

        for message, current_tags in messages:
            message_id = message["id"]

            with st.container(border=True):
                left, right = st.columns([4, 1])

                with left:
                    st.write(message["text"])
                    _render_media(settings, account_id, message)
                    st.caption(
                        f"📅 {message['date'].strftime('%Y-%m-%d %H:%M:%S')} | "
                        f"ID: {message_id}"
                    )

                with right:
                    value = st.text_input(
                        "Tags (comma-separated)",
                        ", ".join(current_tags),
                        key=(
                            f"tags_{account_id}_"
                            f"{selected_chat_id}_{message_id}"
                        ),
                        help=(
                            "Commas separate tags. Empty values are ignored and "
                            "duplicate tags are removed when saved."
                        ),
                    )

                    if st.button(
                        "Save Tags",
                        key=(
                            f"save_{account_id}_"
                            f"{selected_chat_id}_{message_id}"
                        ),
                    ):
                        save_tags(
                            settings.db_file,
                            account_id,
                            selected_chat_id,
                            message_id,
                            value.split(","),
                        )
                        st.rerun()

                    delete_state_key = _delete_state_key(
                        account_id,
                        selected_chat_id,
                        message_id,
                    )
                    if (
                        st.session_state.get("pending_delete_message")
                        == delete_state_key
                    ):
                        st.warning(
                            "Delete this Telegram message permanently?"
                        )
                        confirm_col, cancel_col = st.columns(2)
                        with confirm_col:
                            confirm_delete = st.button(
                                "✅ Confirm",
                                key=(
                                    f"confirm_del_{account_id}_"
                                    f"{selected_chat_id}_{message_id}"
                                ),
                                type="primary",
                                use_container_width=True,
                            )
                        with cancel_col:
                            cancel_delete = st.button(
                                "Cancel",
                                key=(
                                    f"cancel_del_{account_id}_"
                                    f"{selected_chat_id}_{message_id}"
                                ),
                                use_container_width=True,
                            )

                        if cancel_delete:
                            st.session_state.pending_delete_message = None
                            st.rerun()

                        if confirm_delete:
                            try:
                                delete_message(
                                    selected_chat_id,
                                    message_id,
                                )
                                (
                                    st.session_state.messages,
                                    st.session_state.media_files,
                                ) = _remove_message_from_state(
                                    st.session_state.messages,
                                    st.session_state.media_files,
                                    account_id,
                                    selected_chat_id,
                                    message_id,
                                )
                                st.session_state.pending_delete_message = None
                                st.rerun()
                            except Exception as exc:
                                st.session_state.pending_delete_message = None
                                st.error(
                                    f"Failed to delete message: {exc}"
                                )
                    elif st.button(
                        "🗑️ Delete",
                        key=(
                            f"del_{account_id}_"
                            f"{selected_chat_id}_{message_id}"
                        ),
                    ):
                        st.session_state.pending_delete_message = (
                            delete_state_key
                        )
                        st.rerun()


def render_main(settings):
    if (
        not st.session_state.telegram_user
        or not st.session_state.selected_telegram_account_id
    ):
        st.info("Add or select a Telegram account from the sidebar.")
        return

    force_refresh = bool(
        st.session_state.pop("force_refresh_dialogs", False)
    )
    if not st.session_state.dialogs or force_refresh:
        try:
            dialogs, warning = _load_or_refresh_dialogs(
                settings,
                st.session_state.selected_telegram_account_id,
                force_refresh=force_refresh,
            )
            st.session_state.dialogs = dialogs
            if warning:
                st.warning(warning)
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
        st.session_state.message_range_signature = None
        st.session_state.message_result_limit = settings.default_message_limit
        st.rerun()

    _fetch_messages_if_needed(
        settings,
        selected_chat_id,
        start_date,
        end_date,
    )

    _render_message_actions(settings)

    account_id = st.session_state.selected_telegram_account_id
    messages = []
    tags_by_message = get_tags_for_messages(
        settings.db_file,
        account_id,
        selected_chat_id,
        [message["id"] for message in st.session_state.messages],
    )

    for message in st.session_state.messages:
        message_tags = tags_by_message.get(message["id"], [])
        if not _message_matches_filters(
            message,
            message_tags,
            start_date,
            end_date,
            search,
            tag,
        ):
            continue

        messages.append((message, message_tags))

    _render_message_scroll_area(
        settings,
        account_id,
        selected_chat_id,
        messages,
    )
