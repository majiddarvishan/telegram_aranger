from datetime import date, timedelta
from pathlib import Path
import threading
import time

import streamlit as st

from db.dialogs import (
    cache_has_peer_metadata,
    load_dialogs as load_cached_dialogs,
    replace_dialogs,
)
from db.tags import all_tags, get_tags_for_messages, save_tags
from services.telegram_service import (
    delete_message,
    get_dialogs,
    history,
    latest_history,
    start_media_download,
)
from ui.theme import (
    MESSAGE_HEADER_CSS,
    action_summary_html,
    empty_state_html,
    media_meta_html,
    message_body_html,
    message_meta_html,
    tag_chips_html,
)
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


def _tag_editor_state_key(
    account_id: int,
    chat_id: int,
    message_id: int,
) -> str:
    return f"{account_id}:{chat_id}:{message_id}"


def _message_card_key(account_id: int, message_id: int) -> str:
    return f"message-card-{account_id}-{message_id}"


def _message_footer_key(account_id: int, message_id: int) -> str:
    return f"message-footer-{account_id}-{message_id}"


def _display_message_text(message: dict) -> str:
    text = message.get("text", "") or ""
    media = message.get("media") or {}
    media_type = media.get("type")

    if media_type:
        placeholder = f"[{media_type.replace('_', ' ').title()}]"
        if text.strip() == placeholder:
            return ""

    return text


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
        text="Downloading media… 0%",
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
                    text=f"Downloading media… {percent}%{size_text}",
                )
                last_percent = percent

            time.sleep(0.1)

        result = future.result()
        progress_bar.progress(
            100,
            text="Downloading media… 100%",
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

    st.markdown(
        media_meta_html(details),
        unsafe_allow_html=True,
    )

    chat_id = message["chat_id"]
    message_id = message["id"]

    if media_type == "photo":
        preview_key = _media_state_key(
            account_id,
            chat_id,
            message_id,
            "preview",
        )
        prepared = _get_prepared_media(preview_key)

        if prepared is None:
            with st.container(
                key=f"media-actions-{account_id}-{message_id}",
            ):
                preview_col, spacer_col = st.columns([1.3, 6.7])
                with preview_col:
                    if st.button(
                        "Preview photo",
                        key=f"media-photo-{account_id}-{chat_id}-{message_id}",
                        use_container_width=True,
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

    if media_type in ("voice", "audio"):
        preview_key = _media_state_key(
            account_id,
            chat_id,
            message_id,
            "preview",
        )
        prepared = _get_prepared_media(preview_key)
        action_label = "Play voice" if media_type == "voice" else "Play audio"

        if prepared is None:
            with st.container(
                key=f"media-actions-{account_id}-{message_id}",
            ):
                play_col, spacer_col = st.columns([1.3, 6.7])
                with play_col:
                    if st.button(
                        action_label,
                        key=(
                            f"media-audio-{account_id}-"
                            f"{chat_id}-{message_id}"
                        ),
                        use_container_width=True,
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
            mime_type = (
                prepared.get("mime_type")
                or media.get("mime_type")
                or ("audio/ogg" if media_type == "voice" else "audio/mpeg")
            )
            st.audio(
                prepared["path"],
                format=mime_type,
            )
        return

    if media_type in ("video", "video_note", "animation"):
        play_key = _media_state_key(
            account_id,
            chat_id,
            message_id,
            "preview",
        )
        prepared = _get_prepared_media(play_key)

        download_key = _media_state_key(
            account_id,
            chat_id,
            message_id,
            "download",
        )
        download_ready = (
            _get_prepared_media(download_key)
            if media_type == "video"
            else None
        )

        if prepared is None:
            with st.container(
                key=f"media-actions-{account_id}-{message_id}",
            ):
                if media_type == "video" and download_ready is None:
                    play_col, prepare_col, spacer_col = st.columns(
                        [1.2, 1.7, 5.1]
                    )
                else:
                    play_col, spacer_col = st.columns([1.2, 6.8])
                    prepare_col = None

                with play_col:
                    if st.button(
                        "Play video",
                        key=f"media-play-{account_id}-{chat_id}-{message_id}",
                        use_container_width=True,
                    ):
                        prepared = _prepare_media(
                            settings,
                            account_id,
                            chat_id,
                            message_id,
                            "preview",
                            settings.media_preview_max_mb,
                        )

                if prepare_col is not None:
                    with prepare_col:
                        if st.button(
                            "Prepare download",
                            key=(
                                f"media-prepare-download-"
                                f"{account_id}-{chat_id}-{message_id}"
                            ),
                            use_container_width=True,
                        ):
                            download_ready = _prepare_media(
                                settings,
                                account_id,
                                chat_id,
                                message_id,
                                "download",
                                settings.media_download_max_mb,
                            )

        if prepared:
            st.video(prepared["path"])

        if media_type == "video":
            download_ready = download_ready or prepared
            if download_ready:
                path = Path(download_ready["path"])
                with st.container(
                    key=f"media-download-actions-{account_id}-{message_id}",
                ):
                    download_col, redownload_col, spacer_col = st.columns(
                        [1.25, 1.25, 5.5]
                    )

                    with download_col:
                        try:
                            with path.open("rb") as file_handle:
                                st.download_button(
                                    "Download",
                                    data=file_handle,
                                    file_name=download_ready["file_name"],
                                    mime=download_ready["mime_type"],
                                    key=(
                                        f"media-download-"
                                        f"{account_id}-{chat_id}-{message_id}"
                                    ),
                                    use_container_width=True,
                                )
                        except OSError as exc:
                            st.error(f"Failed to open cached video: {exc}")

                    with redownload_col:
                        if st.button(
                            "Redownload",
                            key=(
                                f"media-redownload-"
                                f"{account_id}-{chat_id}-{message_id}"
                            ),
                            help=(
                                "Discard the cached copy and download "
                                "the video again from Telegram."
                            ),
                            use_container_width=True,
                        ):
                            st.session_state.media_files.pop(
                                download_key,
                                None,
                            )
                            st.session_state.media_files.pop(
                                play_key,
                                None,
                            )
                            fresh = _prepare_media(
                                settings,
                                account_id,
                                chat_id,
                                message_id,
                                "download",
                                settings.media_download_max_mb,
                                force_download=True,
                            )
                            if fresh:
                                st.rerun()
        return

    st.info(
        f"{media_type.replace('_', ' ').title()} media is detected. "
        "Preview is not implemented yet."
    )


def _has_saved_messages_dialog(
    dialogs: list[dict],
    self_chat_id: int | None,
) -> bool:
    if self_chat_id is None:
        return True
    return any(dialog.get("id") == self_chat_id for dialog in dialogs)


def _load_or_refresh_dialogs(
    settings,
    account_id: int,
    self_chat_id: int | None = None,
    force_refresh: bool = False,
) -> tuple[list[dict], str | None]:
    cached = load_cached_dialogs(settings.db_file, account_id)
    if (
        cached
        and not force_refresh
        and cache_has_peer_metadata(cached)
        and _has_saved_messages_dialog(cached, self_chat_id)
    ):
        return cached, None

    with _DIALOG_REFRESH_LOCK:
        if not force_refresh:
            cached = load_cached_dialogs(settings.db_file, account_id)
            if (
                cached
                and cache_has_peer_metadata(cached)
                and _has_saved_messages_dialog(cached, self_chat_id)
            ):
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


def _default_chat_id(
    dialogs: list[dict],
    telegram_user: dict | None,
) -> int | None:
    if not dialogs:
        return None

    own_id = (telegram_user or {}).get("id")
    if own_id is not None:
        for dialog in dialogs:
            if dialog.get("id") == own_id:
                return own_id

    for dialog in dialogs:
        if str(dialog.get("title", "")).strip().lower() == "saved messages":
            return dialog["id"]

    return dialogs[0]["id"]


def _chat_label(chat, saved_messages_chat_id: int | None = None):
    if (
        saved_messages_chat_id is not None
        and chat.get("id") == saved_messages_chat_id
    ):
        return "Saved Messages · Private"

    type_label = {
        "private": "Private",
        "group": "Group",
        "supergroup": "Group",
        "channel": "Channel",
    }.get(chat["type"], "Chat")

    parts = [chat["title"]]
    if chat.get("username"):
        parts.append(f"@{chat['username']}")
    parts.append(type_label)

    return " · ".join(parts)


def _latest_message_date_range(messages: list[dict]):
    """Return the inclusive date span covered by a latest-message batch."""
    message_dates = [
        message["date"].date()
        for message in messages
        if message.get("date") is not None
    ]
    if not message_dates:
        return None
    return min(message_dates), max(message_dates)


def _maybe_align_empty_chat_to_latest(
    settings,
    selected_chat_id: int,
    peer_username: str = "",
) -> bool:
    """Show latest messages once when a newly selected chat has an empty range."""
    if (
        st.session_state.get("message_auto_latest_chat_id")
        != selected_chat_id
    ):
        return False

    # One-shot behavior: manual empty date selections after this point
    # must remain exactly as the user chose them.
    st.session_state.message_auto_latest_chat_id = None

    if (
        st.session_state.get("message_fetch_error")
        or st.session_state.messages
    ):
        return False

    try:
        with st.spinner("No messages in this date range. Loading latest…"):
            latest = latest_history(
                selected_chat_id,
                settings.default_message_limit,
                peer_username=peer_username,
                dialog_limit=settings.telegram_dialog_limit,
            )
    except Exception as exc:
        st.warning(
            "No messages were found in the selected date range, and "
            f"the latest messages could not be loaded: {exc}"
        )
        return False

    latest_range = _latest_message_date_range(latest)
    if not latest or latest_range is None:
        return False

    start_date, end_date = latest_range
    result_limit = settings.default_message_limit
    range_signature = (
        selected_chat_id,
        start_date.isoformat(),
        end_date.isoformat(),
    )

    st.session_state.messages = latest
    st.session_state.message_fetch_error = None
    st.session_state.message_result_limit = result_limit
    st.session_state.message_range_signature = range_signature
    st.session_state.message_query_signature = (
        *range_signature,
        result_limit,
    )
    st.session_state.message_date_range = (start_date, end_date)
    _set_pending_date_range(start_date, end_date)
    st.rerun()
    return True


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
MESSAGE_FILTERS_KEY = "message-filters"
MESSAGE_DATE_NAV_KEY = "message-date-nav"
MESSAGE_ACTIONS_KEY = "message-actions"
MESSAGE_SCROLL_KEY = "message-scroll-area"

def _render_message_header(settings, options, current_chat_id, today):
    account_id = st.session_state.selected_telegram_account_id
    tags = all_tags(settings.db_file, account_id)
    start_date, end_date = _prepare_date_range(today)

    with st.container(key=MESSAGE_HEADER_KEY):
        with st.container(key=MESSAGE_FILTERS_KEY):
            chat_col, search_col, tag_col = st.columns([2.7, 2.2, 1.2])

            with chat_col:
                selected_chat_id = st.selectbox(
                    "Chat / Group / Channel",
                    options=list(options),
                    index=list(options).index(current_chat_id),
                    format_func=lambda chat_id: options[chat_id],
                    key="chat_selector",
                    label_visibility="collapsed",
                )

            with search_col:
                search = st.text_input(
                    "Search messages",
                    key="message_search",
                    placeholder="Search messages…",
                    label_visibility="collapsed",
                )

            with tag_col:
                tag = st.selectbox(
                    "Tag",
                    ["All"] + tags,
                    key="message_tag_filter",
                    label_visibility="collapsed",
                )

        with st.container(key=MESSAGE_DATE_NAV_KEY):
            date_col, previous_col, next_col = st.columns([8.0, 1.0, 1.0])

            with date_col:
                picked = st.date_input(
                    "Date range",
                    value=(start_date, end_date),
                    max_value=today,
                    key="message_date_range_picker",
                )

            with previous_col:
                if st.button(
                    "‹",
                    help="Previous day",
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
                    "›",
                    help="Next day",
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


def _fetch_messages_if_needed(
    settings,
    selected_chat_id,
    start_date,
    end_date,
    peer_username: str = "",
):
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
        st.session_state.message_fetch_error = None

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

    with st.spinner("Loading messages…"):
        try:
            start_dt, end_dt = bounds(start_date, end_date)
            st.session_state.messages = history(
                selected_chat_id,
                start_dt,
                end_dt,
                result_limit,
                peer_username=peer_username,
                dialog_limit=settings.telegram_dialog_limit,
            )
            st.session_state.message_fetch_error = None
            st.session_state.message_query_signature = signature
        except Exception as exc:
            st.session_state.message_fetch_error = str(exc)
            st.error(f"Failed to fetch messages: {exc}")
            st.session_state.messages = []
            st.session_state.message_query_signature = signature


def _render_message_actions(
    settings,
    visible_count: int,
) -> None:
    loaded_count = len(st.session_state.messages)
    result_limit = (
        st.session_state.get("message_result_limit")
        or settings.default_message_limit
    )
    can_load_more = loaded_count >= result_limit

    with st.container(key=MESSAGE_ACTIONS_KEY):
        if can_load_more:
            refresh_col, load_more_col, summary_col = st.columns(
                [0.8, 0.95, 6.25]
            )
        else:
            refresh_col, summary_col = st.columns([0.8, 7.2])
            load_more_col = None

        with refresh_col:
            if st.button(
                "Refresh",
                key="refresh_messages",
                use_container_width=True,
            ):
                st.session_state.message_query_signature = None
                st.rerun()

        if load_more_col is not None:
            with load_more_col:
                if st.button(
                    "Load more",
                    key="load_more_messages",
                    use_container_width=True,
                ):
                    st.session_state.message_result_limit = (
                        result_limit + settings.default_message_limit
                    )
                    st.session_state.message_query_signature = None
                    st.rerun()

        with summary_col:
            st.markdown(
                action_summary_html(visible_count, loaded_count),
                unsafe_allow_html=True,
            )


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


def _render_message_footer(
    settings,
    account_id: int,
    chat_id: int,
    message_id: int,
    current_tags: list[str],
) -> None:
    editor_state_key = _tag_editor_state_key(
        account_id,
        chat_id,
        message_id,
    )
    delete_state_key = _delete_state_key(
        account_id,
        chat_id,
        message_id,
    )
    input_key = f"tag-editor-input-{account_id}-{chat_id}-{message_id}"

    is_editing = (
        st.session_state.get("editing_tag_message")
        == editor_state_key
    )
    pending_delete = (
        st.session_state.get("pending_delete_message")
        == delete_state_key
    )

    with st.container(
        key=_message_footer_key(account_id, message_id),
    ):
        if is_editing:
            if input_key not in st.session_state:
                st.session_state[input_key] = ", ".join(current_tags)

            value = st.text_input(
                "Tags",
                key=input_key,
                help="Separate tags with commas.",
            )
            with st.container(
                key=f"message-footer-edit-actions-{account_id}-{message_id}",
            ):
                save_col, cancel_col, spacer_col = st.columns(
                    [0.9, 0.9, 6.2]
                )

                with save_col:
                    if st.button(
                        "Save",
                        key=(
                            f"save-tags-"
                            f"{account_id}-{chat_id}-{message_id}"
                        ),
                        use_container_width=True,
                    ):
                        save_tags(
                            settings.db_file,
                            account_id,
                            chat_id,
                            message_id,
                            value.split(","),
                        )
                        st.session_state.editing_tag_message = None
                        st.session_state.pop(input_key, None)
                        st.rerun()

                with cancel_col:
                    if st.button(
                        "Cancel",
                        key=(
                            f"cancel-tags-"
                            f"{account_id}-{chat_id}-{message_id}"
                        ),
                        use_container_width=True,
                    ):
                        st.session_state.editing_tag_message = None
                        st.session_state.pop(input_key, None)
                        st.rerun()
            return

        with st.container(
            key=f"message-footer-actions-{account_id}-{message_id}",
        ):
            tag_col, edit_col, delete_col = st.columns(
                [6.0, 1.0, 1.0]
            )

            with tag_col:
                if current_tags:
                    st.markdown(
                        tag_chips_html(current_tags),
                        unsafe_allow_html=True,
                    )

            with edit_col:
                if st.button(
                    "Edit tags",
                    key=f"edit-tags-{account_id}-{chat_id}-{message_id}",
                    help="Edit tags for this message.",
                    use_container_width=True,
                ):
                    st.session_state.editing_tag_message = editor_state_key
                    st.session_state[input_key] = ", ".join(current_tags)
                    st.rerun()

            with delete_col:
                if not pending_delete and st.button(
                    "Delete",
                    key=(
                        f"delete-message-"
                        f"{account_id}-{chat_id}-{message_id}"
                    ),
                    help="Delete this message from Telegram.",
                    use_container_width=True,
                ):
                    st.session_state.pending_delete_message = (
                        delete_state_key
                    )
                    st.rerun()

        if not pending_delete:
            return

        st.warning("Delete this message from Telegram? This cannot be undone.")
        with st.container(
            key=f"message-footer-delete-actions-{account_id}-{message_id}",
        ):
            confirm_col, cancel_col, spacer_col = st.columns(
                [1.15, 0.9, 5.95]
            )

            with confirm_col:
                confirm_delete = st.button(
                    "Delete message",
                    key=(
                        f"confirm-delete-message-"
                        f"{account_id}-{chat_id}-{message_id}"
                    ),
                    use_container_width=True,
                )

            with cancel_col:
                cancel_delete = st.button(
                    "Cancel",
                    key=(
                        f"cancel-delete-message-"
                        f"{account_id}-{chat_id}-{message_id}"
                    ),
                    use_container_width=True,
                )

        if cancel_delete:
            st.session_state.pending_delete_message = None
            st.rerun()

        if confirm_delete:
            try:
                delete_message(chat_id, message_id)
                (
                    st.session_state.messages,
                    st.session_state.media_files,
                ) = _remove_message_from_state(
                    st.session_state.messages,
                    st.session_state.media_files,
                    account_id,
                    chat_id,
                    message_id,
                )
                st.session_state.pending_delete_message = None
                st.rerun()
            except Exception as exc:
                st.session_state.pending_delete_message = None
                st.error(f"Failed to delete message: {exc}")


def _render_message_card(
    settings,
    account_id: int,
    chat_id: int,
    message: dict,
    current_tags: list[str],
) -> None:
    message_id = message["id"]
    media = message.get("media") or {}
    media_type = media.get("type")
    media_label = (
        media_type.replace("_", " ").title()
        if media_type
        else None
    )

    with st.container(
        border=True,
        key=_message_card_key(account_id, message_id),
    ):
        st.markdown(
            message_meta_html(
                message["date"].strftime("%Y-%m-%d %H:%M:%S"),
                message_id,
                media_label,
            ),
            unsafe_allow_html=True,
        )

        display_text = _display_message_text(message)
        if display_text:
            st.markdown(
                message_body_html(display_text),
                unsafe_allow_html=True,
            )

        _render_media(settings, account_id, message)

        _render_message_footer(
            settings,
            account_id,
            chat_id,
            message_id,
            current_tags,
        )


def _render_message_scroll_area(
    settings,
    account_id,
    selected_chat_id,
    messages,
):
    with st.container(
        height=settings.message_scroll_height,
        border=True,
        key=MESSAGE_SCROLL_KEY,
    ):
        if not messages:
            if st.session_state.get("message_fetch_error"):
                st.markdown(
                    empty_state_html(
                        "Messages unavailable",
                        (
                            "Telegram could not load this chat. "
                            "Use Refresh to retry."
                        ),
                        "!",
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    empty_state_html(
                        "No messages found",
                        (
                            "No loaded message matches the current chat, "
                            "date range, search or tag filters."
                        ),
                        "0",
                    ),
                    unsafe_allow_html=True,
                )
            return

        for message, current_tags in messages:
            _render_message_card(
                settings,
                account_id,
                selected_chat_id,
                message,
                current_tags,
            )


def render_main(settings):
    if (
        not st.session_state.telegram_user
        or not st.session_state.selected_telegram_account_id
    ):
        st.markdown(
            empty_state_html(
                "No Telegram account selected",
                (
                    "Add or select a Telegram account from the sidebar "
                    "to start browsing messages."
                ),
                "TG",
            ),
            unsafe_allow_html=True,
        )
        return

    force_refresh = bool(
        st.session_state.pop("force_refresh_dialogs", False)
    )
    if not st.session_state.dialogs or force_refresh:
        try:
            dialogs, warning = _load_or_refresh_dialogs(
                settings,
                st.session_state.selected_telegram_account_id,
                self_chat_id=st.session_state.telegram_user.get("id"),
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
        st.markdown(
            empty_state_html(
                "No chats available",
                (
                    "Telegram did not return any chats for this account. "
                    "Use Refresh chats in the sidebar to try again."
                ),
                "0",
            ),
            unsafe_allow_html=True,
        )
        return

    dialogs_by_id = {chat["id"]: chat for chat in dialogs}
    saved_messages_chat_id = st.session_state.telegram_user.get("id")
    options = {
        chat_id: _chat_label(chat, saved_messages_chat_id)
        for chat_id, chat in dialogs_by_id.items()
    }
    current_chat_id = st.session_state.selected_chat_id

    if current_chat_id not in options:
        current_chat_id = _default_chat_id(
            dialogs,
            st.session_state.telegram_user,
        )
        st.session_state.selected_chat_id = current_chat_id
        st.session_state.message_auto_latest_chat_id = current_chat_id

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
        st.session_state.message_auto_latest_chat_id = selected_chat_id
        st.rerun()

    selected_dialog = dialogs_by_id.get(selected_chat_id, {})
    _fetch_messages_if_needed(
        settings,
        selected_chat_id,
        start_date,
        end_date,
        peer_username=selected_dialog.get("username", ""),
    )

    _maybe_align_empty_chat_to_latest(
        settings,
        selected_chat_id,
        peer_username=selected_dialog.get("username", ""),
    )

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

    _render_message_actions(settings, len(messages))

    _render_message_scroll_area(
        settings,
        account_id,
        selected_chat_id,
        messages,
    )
