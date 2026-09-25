# Decisions / Observed Design Choices

These are the current implementation/architecture decisions for **Telegram Harbor** on `main`. Update this file when the user changes a requirement or a later phase supersedes one.

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

## D-021 — Product name is Telegram Harbor
Status: current

The product is named **Telegram Harbor** and behaves as a general Telegram message/media manager for private chats, groups, supergroups, channels, and Saved Messages.

The GitHub repository name remains `telegram_aranger` for now. Persisted compatibility identifiers such as the existing cookie name, default database filename, and Docker volume name are intentionally retained to avoid breaking login persistence or hiding existing data.

## D-022 — Permanent message deletion requires confirmation
Status: current

A first Delete action only enters a pending state. A second explicit confirmation is required before calling Telegram's delete API.

## D-023 — Current tag model stays simple
Status: current

Tags remain comma-separated SQLite text for the current feature scope. Values are trimmed and de-duplicated. A normalized tag table is deferred until global rename/delete, richer tag metadata, or higher-scale querying is required.


## D-024 — YouTube download is an independent workspace
Status: planned on `feature/youtube-download`

YouTube functionality is isolated from Telegram message browsing. The Streamlit UI should expose a separate workspace/tool rather than embedding YouTube download controls inside Telegram message cards.

## D-025 — YouTube download uses a service abstraction
Status: planned

The UI must not call the downloader library directly. URL validation, metadata inspection, format selection, download execution, progress hooks, post-processing, and error normalization belong behind a dedicated service layer.

## D-026 — Save directory is user-supplied
Status: planned

V1 requires the user to provide a filesystem save directory before download.

On a local installation this is a path on the local machine. On a remotely hosted installation this path belongs to the host running Telegram Harbor, not the browser client. The UI must state this clearly.

Hosted/multi-user deployments should support configured allowed roots so Web users cannot write to arbitrary server paths.

## D-027 — Rights/service warning is informational, not a legal determination
Status: planned

Telegram Harbor cannot reliably determine copyright ownership from YouTube metadata. V1 therefore:
- always presents a concise rights/service notice;
- may show stronger warnings when metadata/downloader state indicates restrictions;
- requires explicit user acknowledgement before download;
- does not block ordinarily accessible public content solely because a warning is shown.

## D-028 — No technical access-control bypass
Status: planned

V1 must not introduce mechanisms that bypass DRM, paywalls, private/member-only access controls, login protection, or comparable technical restrictions.

The baseline scope is public content that the downloader can access normally without bypass behavior.

## D-029 — YouTube V1 is single-video, unauthenticated, and non-batch
Status: planned

V1 intentionally excludes playlists, full channels, browser-cookie import, authenticated/private content, batch queues, scheduling, and automatic geo-bypass.

## D-030 — FFmpeg is an operational dependency for full YouTube output support
Status: planned

FFmpeg must be treated as a platform dependency for video/audio merging and audio extraction where required. Windows and Docker setup, capability detection, and user-facing failure messages are part of the feature definition.


## D-031 — YouTube V1 includes one optional subtitle track
Status: planned on `feature/youtube-download`

V1 includes optional subtitle download for a single selected language/track per download job.

The metadata model and UI must distinguish:
- manual subtitles;
- auto-generated captions.

The user explicitly chooses whether to download subtitles and which available track to use.

The preferred subtitle output is SRT. If conversion is unavailable, the actual fallback format (for example VTT/original) must be reported instead of silently renaming the content.

Multiple subtitle languages in one job are deferred so the V1 filename requirement can remain deterministic.

## D-032 — YouTube output basename comes from the video title
Status: planned

The default output basename is the sanitized YouTube video title, not the video ID.

Examples:
- `My Video.mp4`
- `My Video.mp3`
- `My Video.srt`

When a subtitle is included, the media and subtitle files must use the same basename.

Sanitization must preserve a readable title while producing valid Windows/Linux filenames.

## D-033 — Filename collisions are resolved as one output group
Status: planned

Automatic overwrite is not the default.

If the target basename already exists, Telegram Harbor chooses one collision suffix for the whole output group and applies it consistently.

Example:
- `My Video (2).mp4`
- `My Video (2).srt`

This preserves the requirement that media and subtitle files remain obviously paired.
