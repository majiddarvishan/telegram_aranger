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
- [x] Cache Telegram dialogs in SQLite, bound initial/refresh retrieval with `TELEGRAM_DIALOG_LIMIT=100`, serialize uncached refreshes, and make Refresh Chats the explicit network refresh path to avoid repeated GetDialogs FloodWaits.
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
- [x] Move Load More Messages beside Refresh Messages above the scrollable message panel, leaving the panel dedicated to message content; regression coverage added.
- [x] Replace fragile fixed-overlay header/mask approach with a normal-flow header plus a dedicated 420px Streamlit scroll container for messages, structurally preventing header/message overlap.
- [x] Prevent scrolled message cards from visually bleeding through the fixed header by adding a shared opaque fixed backdrop, stacking isolation, and regression coverage.
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


## Release checkpoint v1.0.1
- [x] Telegram Harbor v1.0.1 release checkpoint recorded at `a7648e64f1cd8efc0c098b4eb0a689e6bd94d873`.
- [ ] Create Git tag `v1.0.1` pointing exactly to `a7648e64f1cd8efc0c098b4eb0a689e6bd94d873`; current GitHub connector does not expose tag-ref creation.
- [x] Start `1.0.2-dev` after the checkpoint.
- [x] Increase message-panel default height to 620px and make it configurable with `MESSAGE_SCROLL_HEIGHT`.


## Release checkpoint v1.0.2
- [x] Telegram Harbor v1.0.2 release checkpoint recorded at `9a4c429827ec4e31ef1376ae97b0b074a13dd7e9`.
- [x] VERSION / README / CHANGELOG / branding regression updated for 1.0.2.
- [ ] Create Git tag `v1.0.2` pointing exactly to `9a4c429827ec4e31ef1376ae97b0b074a13dd7e9`; current connector does not expose tag-ref creation.


## Release checkpoint v1.0.3
- [x] Telegram Harbor v1.0.3 release checkpoint recorded at `6c27b0343f7534a2c7ff906f27483791df601fe4`.
- [x] VERSION / README / CHANGELOG / branding regression updated for 1.0.3.
- [ ] Create Git tag `v1.0.3` pointing exactly to `6c27b0343f7534a2c7ff906f27483791df601fe4`; current GitHub connector does not expose tag-ref creation.


## Release checkpoint v1.0.4
- [x] Telegram Harbor v1.0.4 release checkpoint recorded at `0c3144f4d99201a917c9353c788def4df9fb4258`.
- [x] VERSION / README / CHANGELOG / branding regression updated for 1.0.4.
- [ ] Create Git tag `v1.0.4` pointing exactly to `0c3144f4d99201a917c9353c788def4df9fb4258`; current GitHub connector does not expose tag-ref creation.


## GUI redesign backlog

Planning source:
- `.codex/GUI_PLAN.md`
- `docs/GUI_DESIGN_PLAN_FA.md`

### GUI-P0 — Design foundation
- [x] Centralize UI CSS/theme and define semantic design tokens.
- [x] Standardize baseline spacing, radius, borders, shadows and typography.
- [x] Use Streamlit theme variables so the foundation adapts to light/dark mode.
- [x] Add regression coverage for sensitive Streamlit CSS selectors and reusable markup helpers.
- [x] Manually verify the visual result in both Light and Dark themes.

### GUI-P1 — Sidebar
- [x] Compact product branding.
- [x] Improve Web-account presentation.
- [x] Improve Telegram account selector and status hierarchy.
- [x] Move destructive Telegram-account actions into a lower-emphasis Account actions area.
- [x] Collapse proxy/network configuration into an expander.
- [x] Normalize sidebar spacing and action priorities.
- [x] Manually review expanded sidebar on desktop/narrow viewports.

### GUI-P2 — Main toolbar/action bar
- [x] Redesign Chat/Search/Tag hierarchy with cleaner labels.
- [x] Make date navigation more compact.
- [x] Surface visible/loaded message counts in the action bar.
- [x] Normalize Refresh vs Load more visual priority.
- [ ] Evaluate active-filter chips after visual review.

### GUI-P3 — Message cards
- [x] Make message content visually dominant.
- [x] Add compact message metadata.
- [x] Render tags as read-mode chips.
- [x] Make tag editing on-demand.
- [x] De-emphasize Delete until requested while preserving confirmation.
- [x] Normalize media action hierarchy.
- [x] Normalize baseline card spacing.
- [x] Manually verify representative text/photo/video cards on desktop.

### GUI-P4 — Auth and state screens
- [x] Branded centered auth card.
- [x] Dedicated empty states for account/chat/message absence.
- [x] Shared warning/success/error surface styling.
- [x] Review loading treatment and standardize loading microcopy.

### GUI-P5 — Responsive/accessibility
- [x] Add baseline responsive behavior around a 900px breakpoint.
- [x] Preserve safe Streamlit column stacking for narrow layouts.
- [x] Add visible keyboard focus and reduced-motion support.
- [x] Standardize baseline control hit targets.
- [x] Light-mode desktop contrast validation.
- [x] Dark-mode screenshot review completed and adaptive-surface issue fixed in code.
- [x] Re-check Dark mode after pulling the adaptive-surface fix; verified visually.
- [x] Initial narrow screenshot validation performed; control truncation found with Sidebar open.
- [x] Re-validate narrow viewport after compact-workspace wrapping changes; passed with Sidebar open.

### GUI-P6 — Polish
- [x] Consistent application icon treatment; decorative chat-type emoji removed while the anchor remains a brand mark.
- [x] Subtle hover/transition behavior for cards, controls, tags and expanders.
- [x] Active/selected state polish for workspace and selectors.
- [x] Microcopy cleanup for loading, navigation and destructive actions.
- [x] Compact <=700px spacing refinement.
- [x] Initial narrow-viewport screenshot reviewed.
- [x] Final narrow-viewport re-review passed.

### GUI guardrails
- [ ] Do not change Telegram runtime/service behavior as part of visual-only phases.
- [ ] Do not change database/tag/message-history/media-cache semantics without explicit approval.
- [ ] Keep each GUI phase independently reviewable with green CI.


### GUI validation correctness fixes
- [x] Persist Pyrogram peer type/access-hash metadata in SQLite dialog cache and hydrate it on Telegram session restore.
- [x] Upgrade dialog-cache schema to v4 and force one refresh of legacy peer-less cache rows.
- [x] Keep username-first / bounded-dialog recovery as a fallback.
- [x] Show fetch-failure state separately from a true empty-message state.
- [x] Persisted-peer correctness fix is included in `main` via the GUI fast-forward merge.


## Release checkpoint v1.1.0
- [x] Fast-forward merge completed from `gui` into `main`.
- [x] Telegram Harbor v1.1.0 release checkpoint recorded at `4b7325b06cb92c32b56fc8a9a82388f547492ae8`.
- [x] VERSION / README / CHANGELOG / branding regression updated for 1.1.0.
- [x] GUI redesign validation completed in Light, Dark, desktop and narrow layouts.
- [x] SQLite schema v4 peer persistence is included in the release.
- [ ] Create Git tag `v1.1.0` pointing exactly to `4b7325b06cb92c32b56fc8a9a82388f547492ae8`; current GitHub connector does not expose tag-ref creation.


## v1.1.0 follow-up UX fixes
- [x] Keep Sign out inside the Web Account card instead of rendering it outside the card boundary.
- [x] Ensure Saved Messages is present in the dialog cache and selected by default on Telegram account startup.
- [x] Preserve the user's subsequently selected chat across normal reruns.


## Message date-range UX
- [x] Auto-show latest messages when a newly selected chat has no messages in the current date range.
- [x] Synchronize the Date range picker to the oldest/newest dates represented by the latest-message batch.
- [x] Keep the automatic fallback one-shot so later manual empty date selections are preserved.
- [x] Keep Saved Messages as the default startup chat when available.


## v1.1.0 follow-up media/sidebar fixes
- [x] Inline Telegram voice/audio playback using the existing lazy media download/cache path and Streamlit audio player.
- [x] Remove the unsupported Voice preview notice.
- [x] Compact Sign out inside the Web Account card and remove its internal divider.
- [x] Add regression coverage for voice/audio rendering and compact Sign out.


## YouTube download feature

Planning source:
- `.codex/YOUTUBE_PLAN.md`
- `docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`

### YT-P0 — Planning
- [x] Create `feature/youtube-download` from current `main`.
- [x] Keep this phase documentation-only; no production code yet.
- [x] Define V1 as single public YouTube video download.
- [x] Require a user-supplied Save directory.
- [x] Define local-vs-hosted save-path semantics.
- [x] Define general copyright/service notice plus stronger restriction warning.
- [x] Keep warning non-blocking for ordinarily accessible public content after user acknowledgement.
- [x] Do not design DRM/paywall/private/member-only/access-control bypass.
- [x] Keep YouTube downloader behind a service abstraction.
- [x] Record FFmpeg as an operational dependency.
- [x] Include optional single-track subtitle download in V1.
- [x] Define matched title-based filenames for media and subtitles.
- [x] Keep playlists/channels/batch/authenticated content out of V1.

### YT-P1 — Service foundation
- [x] Add downloader dependency behind `services/youtube_service.py`.
- [x] Add FFmpeg capability detection.
- [x] Validate supported YouTube URLs.
- [x] Inspect metadata without downloading media.
- [x] Inspect available subtitle/caption tracks.
- [x] Distinguish manual subtitles from auto-generated captions.
- [x] Normalize subtitle language/type/format information.
- [x] Normalize quality/format information.
- [x] Normalize downloader failures.
- [x] Unit-test service behavior without live YouTube.

### YT-P2 — Save path / filesystem safety
- [x] Add required Save directory input.
- [x] Normalize and resolve user path.
- [x] Verify writable directory.
- [x] Confirm before creating missing directories.
- [x] Sanitize the YouTube title into a shared output basename.
- [x] Save media using `<sanitized-title>.<media-ext>`.
- [x] Save the selected subtitle using the exact same basename.
- [x] Prevent output path escape.
- [x] Add grouped collision policy so media/subtitle suffixes stay aligned.
- [x] Add optional allowed-root configuration for hosted/multi-user mode.
- [x] Test Windows and Linux path handling.

### YT-P3 — Warning / acknowledgement
- [x] Always show concise rights/service notice.
- [x] Surface stronger warning signals from metadata/downloader state.
- [x] Require explicit acknowledgement before download.
- [x] Do not block normally accessible public content solely because a warning exists.
- [x] Do not bypass technical access controls.
- [x] Add warning-state tests.

### YT-P4 — Download engine
- [x] Video + audio mode.
- [x] Audio-only mode.
- [x] Quality presets.
- [x] Optional single subtitle-track download.
- [x] Prefer SRT subtitle output and report VTT/original fallback explicitly.
- [x] Preserve Manual vs Auto-generated provenance in the normalized result.
- [x] Progress-hook normalization.
- [x] FFmpeg merge/extract state.
- [x] Partial-download cleanup/recovery.
- [x] Safe final filename/path reporting.
- [x] Error handling and cleanup.

### YT-P5 — Streamlit UI
- [ ] Add independent YouTube workspace.
- [ ] URL input + Inspect action.
- [ ] Metadata/thumbnail preview.
- [ ] Mode and quality controls.
- [ ] Subtitle enable/disable control.
- [ ] Subtitle language selector with Manual / Auto-generated labeling.
- [ ] Subtitle output-format indication.
- [ ] Save directory control.
- [ ] Warning/acknowledgement UI.
- [ ] Download progress/status.
- [ ] Completed/failure states.
- [ ] Light/Dark/responsive review.

### YT-P6 — Platform / docs
- [ ] Windows FFmpeg setup.
- [ ] Docker FFmpeg setup.
- [ ] Deployment documentation.
- [ ] README update.
- [ ] Manual testing checklist.
- [ ] CI tests with no live YouTube dependency.

### YT-P7 — Manual validation
- [ ] Public test video.
- [ ] Video + audio.
- [ ] Audio only.
- [ ] Manual subtitle download.
- [ ] Auto-generated caption download.
- [ ] Verify media/subtitle share the same basename.
- [ ] Verify collision suffix is shared by the complete output group.
- [ ] Save-directory behavior.
- [ ] Windows path.
- [ ] Docker.
- [ ] Warning flow.
- [ ] Failure paths.
- [ ] Final merge/release review.
