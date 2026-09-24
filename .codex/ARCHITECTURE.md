# Architecture

## High-level flow

```text
Browser
  |
  v
Streamlit app.py
  |
  +--> config/settings.py
  |      -> env / Streamlit secrets
  |
  +--> db/*
  |      -> SQLite (users, web_sessions, telegram_accounts, message_tags)
  |
  +--> ui/auth.py
  |      -> local Web authentication + remember-me cookie
  |
  +--> ui/sidebar.py
  |      -> proxy settings
  |      -> Telegram account selection/login/logout
  |
  +--> ui/main.py
         -> dialogs / messages / search / dates / tags / delete
              |
              v
       services/telegram_service.py
          |              |
          | media        v
          +------> services/media_cache.py
                         |
                         v
                  bounded local cache
                         
       services/telegram_runtime.py
         dedicated asyncio loop/thread
              |
              v
          Pyrogram Client
              |
              v
           Telegram
```

## Entry point: app.py
Execution order on each Streamlit rerun:
1. Ensure an asyncio loop exists for Python 3.14 compatibility.
2. Configure Streamlit page.
3. Load settings.
4. Initialize SQLite schema.
5. Initialize `st.session_state` defaults.
6. If no Web user is in session state, try restoring one from the remember-me cookie.
7. If still unauthenticated, render login/registration and stop.
8. Render sidebar/account controls.
9. Render message browser.

## Web authentication
`ui/auth.py` + `db/users.py` + `db/auth_sessions.py`.

Registration:
- Normalize username to lowercase.
- Require an 8-character minimum in UI.
- Hash password with PBKDF2-HMAC-SHA256 and random salt.
- Insert local user into SQLite.

Login:
- Authenticate against SQLite.
- Optionally create a random remember-me token.
- Store only SHA-256(token) in `web_sessions`.
- Put the raw token in a browser cookie using CookieManager.
- Restore login later by hashing the cookie token and looking it up.

Logout:
- Revoke the current remembered token if present.
- Delete the browser cookie.
- Clear Streamlit session state.

## Telegram account onboarding
`ui/sidebar.py` calls `services/telegram_service.py`.

Phone login sequence:
1. Create in-memory Pyrogram Client.
2. `send_code(phone)`.
3. Verify Telegram code.
4. If Telegram requires 2FA, ask for password and call `check_password`.
5. Export Pyrogram session string.
6. Encrypt it with Fernet.
7. Store Telegram profile + encrypted session in `telegram_accounts`.

Restore:
- Load account row owned by current Web user.
- Decrypt saved session.
- Create/connect an in-memory Pyrogram Client from it.
- Call `get_me()`.

Disconnect:
- Disconnect current client but keep encrypted session in SQLite.

Telegram logout:
- Call Telegram `log_out()`.
- Delete local Telegram account row and its tags.

## Async runtime
`services/telegram_runtime.py` creates one daemon thread and asyncio loop per Streamlit session. Runtime shutdown disconnects the active Pyrogram client before stopping and closing the loop.

The UI stays synchronous. Service wrappers call:
`get_runtime().run(coroutine)`

That method uses:
`asyncio.run_coroutine_threadsafe(coro, loop).result()`

Consequence: ordinary Telegram network work runs on the dedicated event loop, but the Streamlit request/rerun still blocks waiting for completion. `TelegramRuntime` records run count, last wait, and maximum wait so blocking impact is measurable. Media downloads use non-blocking submission plus progress polling.

## Message browsing
`services/telegram_service.py`:
- `get_dialogs()`: returns private/group/supergroup/channel dialogs.
- `history()`: starts Telegram history at the selected `end_dt` using `offset_date`, walks backward to `start_dt`, and applies the configured result limit inside that date range.
- Message text uses `message.text`, then `message.caption`, otherwise a media-aware fallback label.
- Media metadata is normalized for photo, video, animation, document, audio, voice, and video-note messages without downloading the file.
- `download_media()` fetches media only on demand, applies configured size limits, and reuses a bounded local cache.
- `delete_message()`: calls Telegram delete API.

`ui/main.py`:
- Selects chat.
- Selects date range.
- Fetches messages only when query signature changes or Refresh is clicked.
- Performs text search in memory.
- Reads local tags from SQLite.
- Filters by selected tag.
- Saves tags locally.
- Deletes Telegram messages.
- Shows photos lazily after explicit user action.
- Plays video/video-note/animation media lazily with Streamlit video rendering.
- Provides a browser video-download control for Telegram video messages.
- Provides previous/next-day date navigation.

## Data model details

### users
Local Web identities:
- id
- username (unique)
- password_hash
- password_salt
- display_name
- timestamps

### telegram_accounts
Owned by a Web user:
- Telegram user identity/profile fields
- encrypted session blob
- unique `(user_id, telegram_user_id)`

### web_sessions
Persistent Web authentication:
- user_id
- SHA-256 remember-token hash
- expiry timestamp

### message_tags
Current primary key:
- `(telegram_account_id, chat_id, message_id)`
- comma-separated, trimmed/de-duplicated tag string

Legacy rows from the pre-chat-id schema are migrated with `chat_id=0` and are not applied to arbitrary chats.

## Streamlit state
Important keys include:
- `web_user`, `remember_token`
- `telegram_runtime`, `telegram_user`
- Telegram login stage/phone/code hash
- selected Telegram account/chat
- dialogs/messages and message query signature
- proxy fields
- date-range widget state

## External boundaries
1. Telegram MTProto via Pyrogram.
2. Browser cookie via extra-streamlit-components.
3. Local environment / Streamlit secrets.
4. Local SQLite file.

There is no separate REST API, worker service, queue, external identity provider, or remote database in this branch.

## Media download/cache flow

```text
message list
   |
   | metadata only
   v
media control in ui/main.py
   |
   | user clicks Show Photo / Load Video / Prepare Video Download
   v
services.telegram_service.download_media()
   |
   +--> size-limit check
   +--> services/media_cache.py
   |      -> account/chat/message scoped path
   |      -> TTL validation
   |      -> total-cache-size cleanup
   |
   +--> cache hit -> return existing local path
   |
   +--> cache miss -> Pyrogram Client.download_media()
                       |
                       v
                    temp file
                       |
                       v
                  atomic move to cache
```

Media cache defaults:
- directory: `.cache/telegram_media`
- TTL: 24 hours
- total cache limit: 2048 MB
- preview limit: 200 MB per media
- browser video download limit: 200 MB per media

All values are configurable through `MEDIA_*` environment variables.


## Database lifecycle
- SQLite schema version is stored in `schema_meta`; current version is 2.
- Legacy message-tag rows are migrated in place without discarding their tag text.
- Connections use WAL, foreign keys, 30-second busy timeout, and `synchronous=NORMAL`.
- Visible message tags are batch-loaded in one query.
- Online backup/verified restore helpers live under `scripts/`.

## Deployment boundary
- Docker runs one non-root Streamlit process with persistent state under `/data`.
- Process health uses Streamlit `/_stcore/health`.
- Horizontal multi-instance deployment is not supported by the current local SQLite/runtime/cache model; see `docs/SCALING.md`.
