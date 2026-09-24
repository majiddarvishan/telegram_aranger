# Decisions / Observed Design Choices

These are the current implementation/architecture decisions for `feature/media-support`. Update this file when the user changes a requirement or a later phase supersedes one.

## D-001 — Streamlit is the application shell
Status: current

The product is a Streamlit application. UI, session state, authentication screens, account management, and message browsing all run through Streamlit reruns.

## D-002 — Local authentication, no Keycloak
Status: current

The branch intentionally uses its own SQLite-backed Web users rather than Keycloak or another external IdP.

## D-003 — SQLite is the only application database
Status: current

Users, remembered Web sessions, Telegram account metadata/session ciphertext, and local message tags are persisted in one SQLite file.

## D-004 — Telegram sessions are exported and encrypted at rest
Status: current

Pyrogram clients are in-memory. Their exported session string is encrypted with Fernet and saved in SQLite. The application requires the same encryption key to restore accounts later.

Operational implication: loss/rotation of the Fernet key without a migration strategy makes existing Telegram sessions unreadable.

## D-005 — One Telegram client/runtime per Streamlit browser session
Status: current

A dedicated daemon thread and asyncio event loop are stored in Streamlit session state. The runtime holds at most one active Pyrogram client.

## D-006 — Telegram proxy is UI-configurable
Status: current

SOCKS5 proxy support is built in. Current session-state defaults enable proxy at `127.0.0.1:1080`; proxy credentials are optional.

## D-007 — Local tags are not written to Telegram
Status: current

Tags are application metadata stored in SQLite only.

## D-008 — Search/filter is mostly local
Status: current

The application fetches a bounded Telegram history set and then applies text search, date checks, and tag filtering locally in the Streamlit process.

## D-009 — Remember-me uses opaque bearer token + server-side hash
Status: current

The raw random token is kept in the browser cookie. Only SHA-256(token) and expiry are stored server-side.

## D-010 — Preserve the modular architecture
Status: current

The modular implementation separates configuration, persistence, Telegram services/runtime, UI, utilities, scripts, and operational documentation. Future changes should preserve this separation unless a redesign is explicitly requested.

## D-011 — Media is downloaded lazily
Status: current

Telegram message listing carries metadata only. Full media bytes are fetched only after an explicit user action such as photo preview, video playback, or video-download preparation.

Downloaded media is stored in a bounded local cache scoped by Web-selected Telegram account, chat, and message. Cache TTL, total size, preview size, and download size are configurable. Video browser downloads use the cached file and keep the Telegram-facing download separate from the browser-facing download control.

## D-012 — Message tags are chat-scoped
Status: current

Telegram message identifiers are scoped to a chat. Local tags therefore use `(telegram_account_id, chat_id, message_id)` as their identity. Legacy rows from the older two-column key are preserved with `chat_id=0` during migration and are intentionally not applied to arbitrary chats.

## D-013 — Web login security is database-backed
Status: current

Password minimum length is enforced outside the UI, remembered sessions are cleaned up at startup, and failed Web-login attempts are persisted in SQLite by normalized username. Internet-facing deployments should additionally enforce source-IP throttling at the reverse proxy/WAF.

## D-014 — Production cookie policy is explicit
Status: current

Local development defaults to `WEB_COOKIE_SECURE=false` and `SameSite=lax`. HTTPS deployments should set `WEB_COOKIE_SECURE=true`. `SameSite=none` is rejected unless secure cookies are enabled.


## D-015 — History pagination is explicit
Status: current

Telegram history starts from the selected range end and walks backward. The configured message limit applies to results inside the selected range. The UI exposes the current loaded count and a **Load More Messages** action instead of implying that the first page is complete.

## D-016 — Full-history search is not performed per keystroke
Status: current

Text search remains local over messages already loaded for the selected range. A future Telegram server-side/full-history search should be an explicit submitted action with its own pagination/cache semantics, not a network call on each Streamlit rerun.

## D-017 — SQLite is single-host storage
Status: current

SQLite uses WAL, foreign keys, busy timeout, and synchronous=NORMAL. This is appropriate for the current single-instance deployment but is not treated as shared storage for horizontal scaling. Multi-instance deployment requires a shared database/runtime redesign.

## D-018 — Backups bind database state to a Fernet-key fingerprint
Status: current

Database backup uses SQLite's online backup API. Backup metadata may contain a SHA-256 fingerprint of the Fernet key so restore can reject the wrong key, but the raw Fernet key must never be stored in the ordinary database backup artifact.

## D-019 — Structured logs are secret-safe by default
Status: current

Operational logging uses JSON and redacts context fields whose keys indicate passwords, tokens, session strings, API secrets, encryption keys, phone codes, or similar secrets. Logs may identify operational entities such as account/message IDs but must not contain authentication material.

## D-020 — Deployment is one non-root Streamlit container
Status: current

The supported container model is a single non-root Streamlit instance with persistent state under /data and health checking through Streamlit /_stcore/health. Telegram connectivity is user/session-specific and is not part of process readiness.

## D-021 — Product scope is broader than the legacy display name
Status: current

The product behaves as a general Telegram message manager for private chats, groups, supergroups, channels, and Saved Messages. The legacy UI title remains until the user explicitly requests a rename.

## D-022 — Permanent message deletion requires confirmation
Status: current

A first Delete action only enters a pending state. A second explicit confirmation is required before calling Telegram's delete API.

## D-023 — Current tag model stays simple
Status: current

Tags remain comma-separated SQLite text for the current feature scope. Values are trimmed and de-duplicated. A normalized tag table is deferred until global rename/delete, richer tag metadata, or higher-scale querying is required.
