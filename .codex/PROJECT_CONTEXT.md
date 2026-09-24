# Project Context

## Product purpose
**Telegram Harbor** is a local/self-hosted Streamlit Telegram message and media manager using Pyrogram.

The product supports Saved Messages plus private chats, groups, supergroups, and channels. The GitHub repository remains `majiddarvishan/telegram_aranger` for compatibility/history.

## Current branch
- Working branch: `main`
- `main` contains the current media, security, testing, performance, migration, logging, backup, Docker, and Remember Me race fixes.
- Re-check GitHub branch HEAD before making future edits.

## Current capabilities
- Local Web user registration/login.
- PBKDF2-HMAC-SHA256 password hashing with domain-enforced minimum length.
- Remember Me browser sessions with hashed server-side tokens.
- Persistent username-based Web-login throttling.
- Configurable Secure/SameSite cookie policy.
- Multiple Telegram accounts per Web user.
- Telegram phone login, code verification, and 2FA.
- Fernet-encrypted exported Telegram session strings.
- SOCKS5 proxy configuration.
- Private/group/supergroup/channel dialog discovery.
- Date-range message history starting from the selected range end.
- Explicit **Load More Messages** pagination.
- Local search over loaded messages.
- Chat-scoped local message tags.
- Tag trim/de-duplication.
- Permanent Telegram message deletion with confirmation.
- Lazy photo preview.
- Lazy video/video-note/animation playback.
- Browser download for Telegram video messages.
- Real byte-level media download progress.
- Bounded media cache with TTL/size limits.
- Interrupted/corrupt media recovery and explicit **Redownload Video**.
- SQLite schema versioning/migration.
- Database backup/restore helpers.
- Structured JSON logging with sensitive-context redaction.
- Dockerfile + Docker Compose + Streamlit health check.
- GitHub Actions regression and Docker-health CI.

## Technology stack
- Python 3.x
- Streamlit
- Pyrogram 2.0.106
- TgCrypto
- SQLite
- cryptography/Fernet
- python-dotenv
- extra-streamlit-components

## Configuration
Required:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION_ENCRYPTION_KEY`

Web auth/security:
- `WEB_REMEMBER_ME_DAYS=7`
- `WEB_COOKIE_SECURE=false`
- `WEB_COOKIE_SAMESITE=lax`
- `WEB_LOGIN_MAX_ATTEMPTS=5`
- `WEB_LOGIN_WINDOW_MINUTES=15`

Storage/media:
- `TELEGRAM_DB_FILE=telegram_manager.db`
- `MEDIA_CACHE_DIR=.cache/telegram_media`
- `MEDIA_CACHE_TTL_HOURS=24`
- `MEDIA_CACHE_MAX_MB=2048`
- `MEDIA_PREVIEW_MAX_MB=200`
- `MEDIA_DOWNLOAD_MAX_MB=200`
- `MESSAGE_SCROLL_HEIGHT=620`

Operations:
- `LOG_LEVEL=INFO`
- `TELEGRAM_SLOW_CALL_SECONDS=1.0`

Required values are read from environment variables with Streamlit-secrets fallback where supported.

## Persistence model
SQLite tables:
- `schema_meta`: schema version.
- `users`: local Web users.
- `telegram_accounts`: Telegram identity plus encrypted session per Web user.
- `web_sessions`: hashed remember tokens and expiry.
- `web_login_attempts`: login throttling metadata.
- `message_tags`: chat-scoped local tags.

Current message-tag identity:
`(telegram_account_id, chat_id, message_id)`

Legacy tag rows are migrated with `chat_id=0`.

Connections use:
- WAL;
- foreign keys;
- 30-second busy timeout;
- `synchronous=NORMAL`.

## Telegram runtime
Each Streamlit browser session owns one `TelegramRuntime`:
- daemon thread;
- dedicated asyncio loop;
- at most one active Pyrogram client.

Ordinary service calls synchronously wait on `run_coroutine_threadsafe(...).result()`, and wait metrics are recorded. Media download uses non-blocking submission so Streamlit can display transfer progress.

Runtime shutdown disconnects the active Pyrogram client before stopping/closing the loop.

## Media architecture
Message listing returns metadata only. Full media is fetched only on explicit user action.

Cache identity includes:
- Web-selected Telegram account;
- chat;
- message;
- media type/file identity.

A valid cache hit requires freshness and, when Telegram reports it, matching file size. Interrupted `.part` files are purged. A user can force a fresh Telegram copy with **Redownload Video**.

## Security/operations
See:
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/DEPENDENCIES.md`
- `docs/SCALING.md`
- `docs/BACKUP_RESTORE.md`

Important:
- the host administrator remains inside the trust boundary;
- horizontal multi-instance deployment is not supported;
- Pyrogram upstream is archived and should not be replaced silently;
- TgCrypto is installed by this repository and is part of the supported deployment profile.

## Automated validation
GitHub Actions currently covers:
- media cache behavior;
- media metadata and downloads;
- interrupted-download recovery;
- Remember Me restore;
- password/auth/session behavior;
- login throttling;
- Telegram account ownership/CRUD;
- tag migration/isolation;
- history/date-range logic;
- timezone compatibility;
- runtime shutdown/wait metrics;
- SQLite configuration;
- backup/restore;
- structured logging redaction;
- UI state smoke tests;
- Docker build/start + Streamlit health.

## Validation status
Real Telegram/browser validation has been completed successfully with no issues reported, including photo preview, inline video playback, browser video download, and interrupted-download recovery.

`docs/MANUAL_TESTING.md` remains the regression checklist for future releases.


## Release status
- Latest release: `v1.0.1`
- v1.0.1 checkpoint SHA: `a7648e64f1cd8efc0c098b4eb0a689e6bd94d873`
- Current development version: `1.0.2-dev`
