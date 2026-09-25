# Project Context

## Product purpose
**Telegram Harbor** is a local/self-hosted Streamlit Telegram message and media manager using Pyrogram.

The product supports Saved Messages plus private chats, groups, supergroups, and channels. The GitHub repository remains `majiddarvishan/telegram_aranger` for compatibility/history.

## Current branch
- Working branch: `feature/youtube-download`
- Baseline: `main@ff7422284c7850ece9f3db9816cf600ff911a560`.
- This branch is currently documentation/planning only for the YouTube download feature.
- The completed `gui` redesign is already merged into `main`.
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
- Private/group/supergroup/channel dialog discovery with persistent per-account SQLite dialog caching and bounded Telegram refresh.
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
- SQLite schema versioning/migration (current development schema: v4).
- Database backup/restore helpers.
- Structured JSON logging with sensitive-context redaction.
- Dockerfile + Docker Compose + Streamlit health check.
- GitHub Actions regression and Docker-health CI.

## Technology stack
- Python 3.x
- Streamlit
- Pyrogram 2.0.106
- tgcrypto2
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
- `TELEGRAM_DIALOG_LIMIT=100`

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
- `telegram_dialog_cache`: latest cached Telegram dialog snapshot plus Pyrogram peer type/access-hash metadata per Telegram account.

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
- `tgcrypto2` is installed by this repository and provides the `tgcrypto` module used by Pyrogram.

## Windows compatibility
- Crypto acceleration uses `tgcrypto2>=1.3.6,<2`, which exposes the `tgcrypto` import expected by Pyrogram.
- Windows + Python 3.14 crypto acceleration is validated in GitHub Actions.

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
- Latest release: `v1.1.0`
- v1.1.0 checkpoint SHA: `4b7325b06cb92c32b56fc8a9a82388f547492ae8`
- Current version: `1.1.0`


## Dialog startup behavior
- Normal startup first reads `telegram_dialog_cache` from SQLite.
- Telegram `messages.GetDialogs` is not called again on every Streamlit rerun/startup when cache exists.
- The first uncached fetch is bounded by `TELEGRAM_DIALOG_LIMIT` (default 100).
- `Refresh Chats` is the explicit network refresh path.
- Uncached refreshes are serialized with a process-level lock to prevent duplicate concurrent `GetDialogs` calls from multiple Streamlit sessions.
- If an explicit refresh fails and cache exists, the cached dialog list remains usable.


## GUI redesign status
- The GUI redesign is complete and merged into `main`.
- Primary design document: `docs/GUI_DESIGN_PLAN_FA.md`.
- Historical execution backlog: `.codex/GUI_PLAN.md`.
- Completed scope: design system, sidebar, toolbar, message cards, auth/empty states, responsive behavior, accessibility, Light/Dark support, RTL/LTR rendering and final interaction polish.


## Pyrogram peer persistence
- Exported Pyrogram session strings contain authentication/session data but do not contain Pyrogram's peer cache.
- Telegram Harbor therefore persists peer metadata with each dialog-cache snapshot:
  - canonical Pyrogram peer ID;
  - peer type;
  - access hash where required;
  - username when available.
- On Telegram account restore, persisted peer tuples are rehydrated through `client.storage.update_peers(...)` before normal message browsing.
- Legacy dialog-cache rows without peer metadata are intentionally refreshed once after schema v4 migration.
- This prevents cached channel/supergroup IDs from producing `PeerIdInvalid` merely because the process restarted.
- Username/bounded-dialog lazy recovery remains as a fallback for stale or unavailable records.


## Automatic empty-range fallback
- When a chat is selected for the first time in the current UI session, Telegram Harbor first tries the currently selected date range.
- If that range contains no messages and the Telegram request itself succeeded, the app fetches only the newest `default_message_limit` messages for that chat.
- The visible Date range is then synchronized to the oldest/newest dates represented by that latest-message batch.
- The fallback is one-shot per chat selection. If the user later manually chooses an empty range, Telegram Harbor preserves that choice instead of jumping away from it.
- The startup/default chat remains Saved Messages when it is available.


## Planned YouTube download capability
- Planning branch: `feature/youtube-download`.
- No implementation code has been added yet.
- V1 scope: single public YouTube video URL.
- User must provide a Save directory.
- On local installations the path is local to the user machine; on remote deployments it is a server-host path and must be labeled as such.
- Hosted/multi-user mode should support allowed save roots.
- Planned outputs:
  - Video + audio;
  - Audio only;
  - simple quality presets.
- Metadata must be inspected before download.
- UI should show a general copyright/service notice and stronger restriction warnings where signals exist.
- Warning remains non-blocking for ordinarily accessible public content after acknowledgement.
- V1 does not include DRM/paywall/private/member-only/login-protection bypass.
- V1 does not include playlists, channels, browser-cookie import, batch queues, scheduling, or automatic geo-bypass.
- FFmpeg is an expected operational dependency for merging/extraction.
- Downloader behavior must be isolated behind a service layer; Streamlit UI must not depend directly on the downloader library.
- Detailed plans:
  - `.codex/YOUTUBE_PLAN.md`
  - `docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`
