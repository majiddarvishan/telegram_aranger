# Changelog

All notable Telegram Harbor changes are recorded here.

## Unreleased

- Cache Telegram dialogs in SQLite per Telegram account so normal startup does not repeatedly call `messages.GetDialogs`.
- Limit initial/explicit Telegram dialog retrieval to `TELEGRAM_DIALOG_LIMIT` (default 100).
- Make **Refresh Chats** the explicit network refresh path.
- Serialize uncached dialog refreshes inside the process so concurrent Streamlit sessions do not hammer Telegram with duplicate `GetDialogs` requests.
- Fall back to cached chats when an explicit Telegram refresh fails.
- Log `application_ready` only once per Streamlit session instead of every rerun.
- Upgrade SQLite schema to version 3 for dialog-cache persistence.

- Remove Streamlit ScriptRunContext access from Telegram runtime coroutines.
- Pass runtime/client objects from the Streamlit thread into background async Telegram operations instead of re-reading `st.session_state` inside `TelegramRuntime`.
- Add operation names to slow Telegram wait logs, so long calls identify `restore_session`, `get_dialogs`, `history`, etc.
- Add regression coverage preventing Streamlit access from Telegram background coroutines.

- Replace legacy `TgCrypto` with maintained `tgcrypto2` while preserving the `tgcrypto` import used by Pyrogram.
- Add Windows + Python 3.14 CI coverage for crypto acceleration.
- Add Windows recovery instructions for existing environments that show the Pyrogram "TgCrypto is missing" warning.

## 1.0.2 - 2026-09-25

- Increase the dedicated message scroll area from 420px to 620px by default.
- Add `MESSAGE_SCROLL_HEIGHT` so deployments can tune the main message panel height without changing code.
- Move **Load More Messages** out of the scroll panel and place it beside **Refresh Messages**.
- Keep the scroll panel dedicated to message-count/status text and message cards.
- Add regression coverage for the message action-bar layout.

## 1.0.1 - 2026-09-25

- Reworked the message page so the controls stay above a dedicated scrollable message area.
- Moved Previous/Next date navigation into the control header.
- Removed the fragile fixed/sticky overlay approach that caused clipping and message/header overlap.
- Added regression coverage for the dedicated message scroll architecture.
- Preserved all media, tagging, deletion, filtering, and pagination behavior.

## 1.0.0 - 2026-09-24

Initial stable Telegram Harbor release checkpoint.

Highlights:
- Telegram Harbor product branding.
- Local multi-user Web authentication with Remember Me.
- Multiple Telegram accounts per Web user.
- Telegram phone/code/2FA login and encrypted session persistence.
- Private chat, group, supergroup, channel, and Saved Messages browsing.
- Date-range history with Load More pagination.
- Search and chat-scoped local tags.
- Lazy photo preview.
- Inline video/video-note/animation playback.
- Browser video download with real transfer progress.
- Bounded media cache and interrupted-download recovery.
- Confirmed Telegram message deletion.
- SQLite schema migration/versioning and backup/restore helpers.
- Structured secret-safe JSON logging.
- Docker/Compose deployment and health checks.
- Automated GitHub Actions regression and Docker-health validation.
- Real Telegram/browser media validation completed successfully.

Release checkpoint commit:
`bd8c8b211aa8e3ee5ca09c864b3e4803eac6807b`
