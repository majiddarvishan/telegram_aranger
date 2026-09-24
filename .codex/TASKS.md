# Tasks / Technical Findings

No source-code fixes were made during the 2026-09-24 review. Items below are findings for future work.

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
- [ ] Manually verify photo preview, inline video playback, and browser video download with small and large Telegram media.

### P1 media validation status
- Pure cache tests were executed successfully in the available local runtime.
- Telegram-service tests were added but could not be executed in this chat runtime because Pyrogram/Streamlit are not installed there and direct GitHub checkout is network-blocked.
- Real Telegram/browser manual verification remains open below.

### Media implementation preference
- Prefer **lazy loading**: listing messages must not automatically download full-size photos/videos.
- Photo preview may use a downloaded thumbnail/small representation when practical.
- Video playback should fetch media only when the user requests playback/preview.
- Video download must be a separate explicit action/button.
- Do not keep unbounded Telegram media on disk.


## P1 — Tests and regression safety
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
- [ ] Consider server-side/Telegram-side search strategy for large histories.
- [ ] Measure the impact of synchronous `.result()` waits on Streamlit responsiveness.
- [ ] Review SQLite contention under multiple concurrent Streamlit users.
- [ ] If multi-instance deployment is required, replace local Streamlit session/runtime assumptions and local SQLite with shared infrastructure.

## P2 — Data model / lifecycle
- [x] Add SQLite `schema_meta` / `schema_version` tracking and a versioned migration path for chat-scoped message tags.
- [ ] Normalize tags if richer tag features are planned instead of comma-separated text.
- [ ] Define backup/restore for the SQLite database and Fernet key as one operational unit.
- [ ] Consider indexes after real query profiling.

## P3 — Operations
- [ ] Add structured logging and useful error context without leaking tokens, phone codes, passwords, session strings, or API secrets.
- [ ] Add Dockerfile and deployment documentation if container deployment is desired.
- [ ] Add health/readiness strategy appropriate for Streamlit + Telegram dependencies.
- [ ] Add dependency/security update policy; Pyrogram is pinned while other packages use ranges.
- [ ] Reconcile documentation claiming TgCrypto is optional with `requirements.txt` currently installing it unconditionally.

## P3 — UX / product definition
- [ ] Clarify whether the intended product is truly "Saved Messages Manager" or a general Telegram chat/message manager; current code lists all supported dialogs.
- [x] Surface loaded/visible counts, current message limit, end-of-range state, and an explicit `Load More Messages` action.
- [ ] Decide whether message deletion should require confirmation.
- [ ] Decide whether tag edits should support commas, normalization, rename, and deletion workflows.

## Review baseline
Branch before context commit:
- `others@5e7d1943b6289dc8c7def7f2a5426097016cc4c3`
- Compared with `main@76f7b4e56ec21873b6ede338f0800cc9c33df2f4`: ahead 5, behind 0.
