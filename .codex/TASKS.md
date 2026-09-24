# Tasks / Technical Findings

This file began as the 2026-09-24 review backlog and now tracks implementation status for **Telegram Harbor** on `main`. Completed items reflect committed code/docs/tests; do not mark real-device/manual validation complete unless it was actually performed.

## P0 — Correctness
- [x] Fix tag identity: `message_tags` now uses `(telegram_account_id, chat_id, message_id)` with an in-place migration that preserves legacy rows under `chat_id=0`.
- [x] Rework historical message retrieval to start from the requested `end_dt` via Pyrogram `offset_date` and apply the result limit inside the requested range.
- [x] Treat `default_message_limit` as the maximum number of returned messages inside the selected date range; `limit=0` is supported internally for unlimited test/service retrieval.
- [x] Verify timezone handling end-to-end: Streamlit calendar dates, local naive bounds, Pyrogram `datetime.timestamp()` offsets, and `datetime.fromtimestamp()` message dates consistently use the server-local timezone; covered by regression tests.
- [x] Ensure stopping a `TelegramRuntime` disconnects the active Pyrogram client before stopping/closing the event loop, including failure-safe and idempotent shutdown tests.


## P1 — Media viewing and download
- [x] Recover safely from interrupted media downloads: purge stale `.part` files, validate cached file size against Telegram metadata, auto-redownload invalid cache entries, and provide a manual **Redownload Video** action.
- [x] Extend Telegram message mapping in `services/telegram_service.py` to expose media metadata instead of collapsing all non-text content to `[Media / File]`.
- [x] Detect and distinguish at least `photo`, `video`, `animation/GIF`, `document`, `audio`, `voice`, and `video_note` so the UI can render the correct control.
- [x] Preserve message text/caption together with media metadata.
- [x] Add inline photo preview in the message card.
- [x] Add inline video playback in the message card using Streamlit video rendering.
- [x] Add an explicit **Download Video** button for video messages so the user can download the video file through the browser.
- [x] Preserve a meaningful video file name and MIME type when Telegram metadata provides them; otherwise generate a stable fallback file name.
- [x] Use lazy/on-demand media download rather than downloading every media item while listing messages.
- [x] Add a visible loading/progress state while media is fetched from Telegram.
  - Shows real byte-level percentage (`0%` to `100%`) and downloaded/total size during Telegram transfer.
- [x] Add temporary media caching so replaying/re-rendering does not repeatedly download the same media unnecessarily.
- [x] Define cache location, cache key, expiry/cleanup behavior, and a maximum disk-usage policy.
- [x] Add configurable maximum preview/download size safeguards for very large videos/files.
- [x] Handle unavailable/deleted/expired media and Telegram download errors without breaking the rest of the message list.
- [x] Ensure media cache/download paths cannot collide between different Telegram accounts, chats, or messages.
- [x] Ensure temporary media is ignored by Git and does not leak Telegram session/authentication data.
- [x] Keep message deletion behavior working for media messages exactly as it does for text messages.
- [x] Verify captions, tags, search result rendering, and date filtering still work for media messages.
- [x] Add tests for media-type detection and metadata mapping.
  - Coverage: all supported media types (`photo`, `video`, `animation`, `document`, `audio`, `voice`, `video_note`) plus normalized metadata fields and text/caption fallback behavior.
- [x] Add tests for lazy download/cache behavior.
- [x] Add tests for video download naming/MIME behavior and failure paths.
- [x] Manually verified photo preview, inline video playback, browser video download, and interrupted-download recovery with real Telegram media; user reported no issues.

### P1 media validation status
- Pure cache tests were executed successfully in the available local runtime.
- The full automated regression suite has executed successfully in GitHub Actions; subsequent commits continue to run the same CI plus Docker health verification.
- Real Telegram/browser manual verification completed successfully.

### Media implementation preference
- Prefer **lazy loading**: listing messages must not automatically download full-size photos/videos.
- Photo preview may use a downloaded thumbnail/small representation when practical.
- Video playback should fetch media only when the user requests playback/preview.
- Video download must be a separate explicit action/button.
- Do not keep unbounded Telegram media on disk.


## P1 — Tests and regression safety
- [x] Prevent browser-side Remember Me cookie write/delete races by avoiding immediate Streamlit reruns after CookieManager set/delete operations; regression tests added.
- [x] Fix and cover Remember Me regression after application restart: refresh browser cookies instead of relying on the CookieManager constructor snapshot.
- [x] Add unit tests for password hashing/authentication.
- [x] Add tests for remember-me token creation, expiry, restore, and revocation.
- [x] Add database tests for ownership isolation between Web users, including protection of another user's account tags during delete attempts.
- [x] Add tests for Telegram account save/update/delete behavior.
- [x] Add tests for tag identity across multiple chats and legacy schema migration.
- [x] Add service tests around date-range/history behavior using an injectable fake Telegram client.
- [x] Add UI smoke coverage for remembered-login restore plus account-selection, filtering, and deletion state transitions.
- [x] Add a minimal GitHub Actions CI workflow on Python 3.12 running `unittest discover`.

## P1 — Security hardening
- [x] Make production cookie policy explicit and configurable with `WEB_COOKIE_SECURE` / `WEB_COOKIE_SAMESITE`; document HTTPS/reverse-proxy requirements.
- [x] Add persistent username-based Web-login throttling with configurable attempt/window limits; recommend proxy/WAF IP throttling for Internet-facing deployments.
- [x] Enforce the minimum password policy in `db.users.create_user()` / `validate_password()`, not only in Streamlit UI.
- [x] Add startup cleanup for expired or malformed `web_sessions`.
- [x] Define Fernet key backup/rotation and rollback procedure in `docs/SECURITY.md`.
- [x] Review proxy credentials: keep per-user values session-only today; document secret-manager preference for shared production proxy credentials.
- [x] Document multi-user trust boundaries, host/database access, Telegram session sensitivity, and stronger-isolation requirements in `docs/SECURITY.md`.

## P2 — Performance / scalability
- [x] Eliminate per-message N+1 SQLite tag lookups with `get_tags_for_messages()` batch loading.
- [x] Add range-aware history retrieval plus `Load More Messages` result pagination in increments of `default_message_limit`.
- [x] Define search strategy: keep search local over explicitly loaded range pages to avoid per-keystroke Telegram calls; document an explicit-submit `search_messages()` design for future full-history search.
- [x] Instrument `TelegramRuntime.run()` with call count / last wait / max wait metrics so blocking Telegram operations can be measured before converting more UI paths to async/progress flows.
- [x] Review and harden SQLite concurrency with WAL, 30s `busy_timeout`, `synchronous=NORMAL`, batched tag reads, and regression tests.
- [x] Document that multi-instance deployment is unsupported by the current local-runtime/SQLite/cache architecture and define the required shared-state redesign in `docs/SCALING.md`.

## P2 — Data model / lifecycle
- [x] Add SQLite `schema_meta` / `schema_version` tracking and a versioned migration path for chat-scoped message tags.
- [x] Keep the current simple comma-separated tag storage for present scope, but trim/de-duplicate tags consistently; defer normalized tag tables until rename/delete/richer metadata is required.
- [x] Add `docs/BACKUP_RESTORE.md` plus SQLite online backup/restore helpers that bind backups to a Fernet-key fingerprint without storing the key in the DB backup.
- [x] Review current hot queries and retain existing PK/unique/index coverage; defer additional indexes until measured query profiling demonstrates a need.

## P3 — Operations
- [x] Add JSON structured logging with sensitive-context redaction plus slow Telegram wait events; do not log raw tokens/passwords/session strings/API secrets.
- [x] Add non-root `Dockerfile`, `docker-compose.yml`, `.dockerignore`, persistent `/data` layout, and `docs/DEPLOYMENT.md`.
- [x] Add Streamlit `/_stcore/health` container healthcheck and document that per-user Telegram connectivity is not part of process readiness.
- [x] Add `docs/DEPENDENCIES.md` with pinned-vs-ranged update policy and explicit Pyrogram archived/upstream-risk handling.
- [x] Reconcile TgCrypto documentation: upstream can run without it, but this repository installs it and treats it as part of the supported deployment profile.

## P3 — UX / product definition
- [x] Fix fixed-header clipping/overflow with Streamlit toolbar and collapsed sidebar: explicit viewport width override, safe collapsed-sidebar default, expanded-sidebar offset, opaque background, and regression coverage.
- [x] Keep the message filter/control area truly fixed in the viewport while message content scrolls, and move Previous/Next date navigation from the bottom into the same fixed header; regression coverage included.
- [x] Rename the product to **Telegram Harbor** across UI, documentation, Docker/CI naming, logger namespaces, and project context while preserving persisted compatibility identifiers.
- [x] Surface loaded/visible counts, current message limit, end-of-range state, and an explicit `Load More Messages` action.
- [x] Require an explicit second-step confirmation before permanently deleting a Telegram message.
- [x] Define current tag semantics: commas are separators; values are trimmed/deduplicated; removing a tag from the field removes it from that message; global rename/delete remains intentionally out of scope until richer tag management is requested.

## Current completion summary
- P0 correctness: complete.
- P1 implementation/tests/security: complete, including real Telegram/browser media validation.
- P2 performance/data lifecycle: complete for current single-instance scope.
- P3 operations/UX: complete for current scope.
- GitHub Actions regression + Docker health: green on recent branch commits.
- Real Telegram/browser validation has been completed successfully; the feature work is merged into `main`.

## Review baseline
Branch before context commit:
- `others@5e7d1943b6289dc8c7def7f2a5426097016cc4c3`
- Compared with `main@76f7b4e56ec21873b6ede338f0800cc9c33df2f4`: ahead 5, behind 0.


## Release checkpoints
- [x] Telegram Harbor v1.0.0 release checkpoint recorded at `bd8c8b211aa8e3ee5ca09c864b3e4803eac6807b` with root `VERSION=1.0.0`, sidebar version display, branding test, README version, and green CI.

- [ ] Create Git tag `v1.0.0` pointing exactly to `bd8c8b211aa8e3ee5ca09c864b3e4803eac6807b`. The currently connected GitHub write actions do not expose tag-ref creation; do not move this release tag to later sticky-header commits.
