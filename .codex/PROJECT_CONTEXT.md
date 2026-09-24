# Project Context

## Product purpose
This branch implements a local/self-hosted Telegram archive/browser Web application using Streamlit and Pyrogram.

Primary capabilities observed in code:
- Local Web user registration and login.
- Optional persistent "Remember me" browser login.
- Multiple Telegram accounts per Web user.
- Telegram phone login, code verification, and Telegram 2FA.
- Encrypted storage of exported Telegram session strings.
- SOCKS5 proxy configuration from the sidebar.
- Telegram dialog discovery for private chats, groups, supergroups, and channels.
- Message browsing by date range.
- Client-side text search over fetched messages.
- Local per-message tagging.
- Telegram message deletion.
- Lazy photo preview.
- Lazy inline playback for video/video-note/animation media.
- Browser download for Telegram video messages.
- Bounded temporary media cache with configurable TTL and size limits.
- Telegram account disconnect or full Telegram logout/removal.

## Technology stack
- Python
- Streamlit: Web UI and per-browser-session state.
- Pyrogram 2.0.106: Telegram MTProto client.
- TgCrypto: optional acceleration in Pyrogram behavior, although currently listed as an install requirement.
- SQLite: application persistence.
- cryptography/Fernet: encryption of Telegram session strings at rest.
- python-dotenv: local configuration.
- extra-streamlit-components: CookieManager used for persistent Web login.

## Configuration
Required:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION_ENCRYPTION_KEY`

Optional:
- `TELEGRAM_DB_FILE` (default: `telegram_manager.db`)
- `WEB_REMEMBER_ME_DAYS` (default: 7)
- `MEDIA_CACHE_DIR` (default: `.cache/telegram_media`)
- `MEDIA_CACHE_TTL_HOURS` (default: 24)
- `MEDIA_CACHE_MAX_MB` (default: 2048)
- `MEDIA_PREVIEW_MAX_MB` (default: 200)
- `MEDIA_DOWNLOAD_MAX_MB` (default: 200)

Configuration is read from environment variables first and Streamlit secrets as a fallback for required values.

## Persistence model
SQLite tables created by `db/database.py`:
- `users`: local Web accounts.
- `telegram_accounts`: Telegram identity plus encrypted exported Pyrogram session per Web user.
- `web_sessions`: persistent Web-login token hashes and expiry.
- `message_tags`: local tags attached to Telegram message IDs.

SQLite uses WAL mode and foreign keys on every opened connection.

## Security model observed
- Passwords: PBKDF2-HMAC-SHA256, 310,000 iterations, random 32-byte salt.
- Remember-me token: generated with `secrets.token_urlsafe(48)`; only SHA-256 token hash is stored in SQLite.
- Telegram session string: encrypted with a configured Fernet key before storage.
- Telegram 2FA password and phone login codes are used transiently and are not intentionally persisted.
- `.env` and SQLite database files are ignored by Git.

## Telegram connection model
Each Streamlit Web session owns a `TelegramRuntime` stored in `st.session_state`.
The runtime starts a daemon thread with a dedicated asyncio event loop. Synchronous UI code submits Pyrogram coroutines to that loop using `asyncio.run_coroutine_threadsafe(...).result()`.

Only one active Pyrogram client is stored in that runtime at a time. Switching Telegram accounts disconnects the previous client.

## Current branch relationship
At review time:
- `main` base: `76f7b4e56ec21873b6ede338f0800cc9c33df2f4`
- `others` head before documentation: `5e7d1943b6289dc8c7def7f2a5426097016cc4c3`
- GitHub comparison: `others` is 5 commits ahead and 0 behind.
- The branch heavily refactors a formerly much larger `app.py` into `config/`, `db/`, `services/`, `ui/`, and `utils/`.

## Current dependency pins
From `requirements.txt`:
- `streamlit>=1.48,<2`
- `pyrogram==2.0.106`
- `TgCrypto>=1.2.5`
- `cryptography>=44,<47`
- `python-dotenv>=1.0,<2`
- `extra-streamlit-components>=0.1.81,<1`

## Operational notes
- `app.py` contains a Python 3.14 compatibility workaround to ensure an asyncio event loop exists before Pyrogram import/use.
- Proxy use defaults to enabled with `127.0.0.1:1080` unless the user disables it in the sidebar.
- Default message fetch limit is 100.
- Default date range is the latest 7 calendar days.
- Media feature tests now exist on `feature/media-support`; the original reviewed `others` baseline had no automated tests.
- Docker files, CI configuration, schema migration tooling, and structured logging are still absent.
