# Session Notes

## 2026-09-24 — Repository review and context bootstrap

User request:
- Review `https://github.com/majiddarvishan/telegram_aranger`.
- Focus on branch `others`.
- Understand the project completely enough to continue development later.
- Create `.codex` and persist useful project context there.

Work performed:
- Confirmed repository access and push permission.
- Confirmed branch `others`.
- Read the complete repository tree for `others`.
- Reviewed entry point, configuration, database/authentication code, Telegram runtime/service, Streamlit UI, utility code, requirements, environment example, and README.
- Compared `others` with `main`.
- Recorded architecture, current design choices, operational model, and prioritized technical findings.
- No application/source code was changed.

Key findings:
- `others` is 5 commits ahead of `main` and 0 behind at the reviewed baseline.
- It is a major modular refactor/reimplementation of the application.
- Local Web auth uses PBKDF2; persistent login stores only hashed remember tokens.
- Telegram session strings are exported, encrypted with Fernet, and stored in SQLite.
- Each Streamlit session owns a background asyncio runtime thread and one active Pyrogram client.
- Message browsing is bounded by a default 100-message Telegram history call.
- Local tag primary key lacks `chat_id`, creating a correctness risk across chats.
- No automated tests/CI/schema migrations were present.

Future session startup:
1. Read `.codex/START_HERE.md`.
2. Read `.codex/TASKS.md`.
3. Confirm branch is still `others` unless the user says otherwise.
4. Re-check branch head before making changes so these notes are not treated as newer than the code.

## 2026-09-24 — Media-support planning branch

User request:
- Create a new branch from current `main`.
- Do not implement media code yet.
- Add planned support for posts containing photos and videos.
- Add inline video playback.
- Add a dedicated video download button so users can download video files through the browser.

Actions:
- Created branch `feature/media-support` from `main@e114a4e886ac046e140bc00c340796b51c3de3aa`.
- Added a detailed media implementation backlog to `.codex/TASKS.md`.
- Preferred approach recorded as lazy/on-demand Telegram media loading with bounded temporary caching.
- No application/source code was changed in this planning step.

Next implementation entry point:
1. Start with media metadata mapping in `services/telegram_service.py`.
2. Add photo/video rendering and explicit video download controls in `ui/main.py`.
3. Add bounded temporary cache/download lifecycle.
4. Add tests and manual verification.

## 2026-09-24 — P1 media implementation

Implemented step-by-step on `feature/media-support`.

### Step 1 — Media metadata
- Added normalized media detection for photo, video, animation, document, audio, voice, and video-note messages.
- Preserved message text/caption and added media metadata without downloading file bytes.

### Step 2 — Lazy download and cache
- Added `services/media_cache.py`.
- Added account/chat/message-scoped media cache paths.
- Added TTL cleanup and maximum total cache size cleanup.
- Added size limits for preview and browser download.
- Added lazy Telegram media download through Pyrogram.
- Added stable/sanitized file names, MIME handling, cache reuse, and failure handling.
- Added `MEDIA_*` configuration and ignored the media cache in Git.

### Step 3 — Streamlit media UI
- Added explicit lazy photo preview.
- Added lazy inline video/video-note/animation playback.
- Added explicit video download preparation and browser `Download Video` control.
- Added loading spinner and readable media metadata.
- Kept existing tags, date/search filtering, and message-delete flow intact.

### Step 4 — Tests and docs
- Added `tests/test_media_cache.py`.
- Added `tests/test_telegram_media.py`.
- Executed the pure cache test scenarios successfully in the available local runtime.
- Could not execute Pyrogram/Streamlit-dependent tests in the chat runtime because those packages are unavailable and direct GitHub network access from the execution container is blocked.
- Updated README and `.codex` architecture/context/decisions/tasks.

### Remaining validation
- Manual verification with a real Telegram account is still required for photo rendering, inline playback, and browser download using representative small/large videos.

## 2026-09-24 — Media metadata test coverage checkpoint

User requested implementation to continue only through:
`Add tests for media-type detection and metadata mapping.`

Completed/validated at this checkpoint:
- Media metadata extraction exists for all supported media types.
- Test coverage now explicitly checks `photo`, `video`, `animation`, `document`, `audio`, `voice`, and `video_note`.
- Tests verify normalized MIME defaults where applicable.
- Tests verify common metadata mapping: file ID, unique ID, file name, MIME type, file size, width, height, and duration.
- Tests verify no-media behavior.
- Tests verify message-text precedence: text -> caption -> media label -> generic message label.

No additional implementation work beyond this requested checkpoint was performed in this step.

## 2026-09-24 — Media download percentage

User requested a real percentage indicator for the existing "Downloading media from Telegram..." state.

Implemented:
- Added non-blocking coroutine submission support to `TelegramRuntime`.
- Added a thread-safe media download progress tracker.
- Wired Pyrogram `download_media(progress=...)` byte callbacks into the tracker.
- Streamlit now renders a real percentage from 0 to 100 while the Telegram transfer is active.
- When total size is known, UI also shows downloaded size / total size.
- Progress is polled every 100 ms on the Streamlit thread; Streamlit UI is not called from the Telegram runtime thread.
- Cache hits complete immediately and end at 100%.
- Added a unit test proving byte progress callbacks reach the download layer.

## 2026-09-24 — Remember Me restart bug

Observed symptom:
- User checked Remember Me, but restarting/reopening the application returned to the Web login screen.

Root cause:
- `CookieManager` was intentionally stored in `st.session_state`.
- Its constructor captures an initial cookie snapshot through a custom Streamlit component.
- On a fresh session that first snapshot can be the component default before browser cookies are hydrated.
- The persisted manager instance then kept that stale snapshot, while `restore_remembered_user()` used `manager.get()` and never refreshed browser cookies.

Fix:
- `restore_remembered_user()` now explicitly calls `CookieManager.get_all()` using a stable restore component key.
- The first empty snapshot is treated as browser-component hydration and execution stops for one component-driven rerun before deciding there is no remembered cookie.
- Persistent cookie expiry now uses UTC and also sets `max_age`.
- Remember-cookie clearing now refreshes browser cookies first, revokes the DB token, and deletes the browser cookie reliably.
- Added regression tests for stale snapshot restore, first hydration, true no-cookie state, and cookie revocation.

No Telegram account/session logic was changed by this fix.

## 2026-09-24 — Interrupted video download recovery

Observed symptom:
- A video download was interrupted by stopping the application.
- The remaining/cached video was corrupted.
- Later attempts treated the cached file as usable and did not reliably fetch a clean copy.

Root cause:
- Cache validity previously checked only file existence + TTL.
- A truncated/corrupted cache entry could therefore be treated as a valid cache hit.
- Abrupt process shutdown can also leave temporary `.part` files because Python cleanup/finally blocks cannot run after process termination.

Fix:
- Cache validation now optionally compares local size with Telegram's reported `file_size`.
- Zero-byte or size-mismatched cache files are invalid.
- Invalid final cache entries are removed automatically before retrying Telegram download.
- Stale `.part` files are removed immediately during cache cleanup, regardless of TTL.
- After a Telegram download completes, the final file size is verified before it is accepted into cache.
- If the completed size does not match Telegram metadata, the file is deleted and an error asks the user to retry.
- Added `force_download` support and a UI **Redownload Video** button that discards the cached copy and fetches a fresh copy from Telegram.
- Added regression tests for truncated cache detection, crash-leftover part cleanup, automatic corrupted-cache recovery, and forced re-download.

Recovery for an already broken video:
- Re-open the message and click **Redownload Video**.
- If the cached file is size-mismatched, even normal Prepare/Load now invalidates and re-downloads it automatically.

## 2026-09-24 — P1 regression and security hardening

Completed:
- Added password hashing/authentication tests.
- Added remembered-session creation/expiry/revocation/cleanup tests.
- Added Web-user ownership tests for Telegram accounts and account deletion.
- Fixed a discovered ownership bug where a non-owner delete attempt could remove another account's tags.
- Migrated message-tag identity to `(telegram_account_id, chat_id, message_id)` while preserving legacy rows under `chat_id=0`.
- Added tag migration/isolation tests.
- Reworked history retrieval to start at requested `end_dt` with Pyrogram `offset_date`, avoiding the previous newest-100-message trap.
- Added injectable fake-client history tests.
- Extracted testable UI state transitions for account switching, filtering, and delete cleanup.
- Added UI state smoke tests.
- Added GitHub Actions CI on Python 3.12.
- Added explicit secure-cookie/SameSite settings.
- Added database-backed username login throttling.
- Moved minimum password enforcement into the domain/database layer.
- Added expired/malformed remembered-session cleanup at startup.
- Added `docs/SECURITY.md` covering HTTPS, reverse proxy, Fernet key backup/rotation, proxy credentials, media-cache security, and multi-user threat model.

CI note:
- Initial workflow failures were traced to invoking test files directly, which changed Python import roots.
- Workflow was corrected to run each file through `python -m unittest discover`.


## 2026-09-24 — P2/P3 completion and validation

Continued implementation after P1.

### P0 correctness closed
- Message tags are now keyed by Telegram account + chat + message.
- Legacy tag rows are migrated with chat_id=0.
- History retrieval starts at the requested date-range end via Pyrogram offset_date.
- Result limits apply inside the requested range and the UI supports Load More.
- Date-range/Pyrogram timezone semantics are explicitly server-local and regression tested.
- TelegramRuntime shutdown disconnects the active client before stopping/closing the loop.

### P1 regression/security closed
- Added broad authentication/session/account/tag/history/UI regression coverage.
- Added persistent username-based login throttling.
- Added explicit Secure/SameSite cookie configuration.
- Enforced password policy in the domain layer.
- Added expired remembered-session cleanup.
- Documented HTTPS, key rotation, proxy secret handling, and multi-user trust boundaries.

### P2 performance/data lifecycle closed
- Eliminated N+1 tag reads using batch loading.
- Added explicit Load More pagination.
- Instrumented synchronous Telegram runtime wait duration.
- Hardened SQLite concurrency settings.
- Added schema version tracking.
- Added online database backup and verified restore helpers.
- Kept the simple tag model but added trim/de-duplication.
- Documented search strategy, indexing policy, and the unsupported multi-instance boundary.

### P3 operations/UX closed
- Added secret-safe JSON structured logging.
- Added non-root Dockerfile, Docker Compose, .dockerignore, persistent /data layout, and Streamlit healthcheck.
- Added deployment/dependency/scaling/backup documentation.
- Reconciled TgCrypto documentation with actual requirements.
- Clarified general Telegram-manager product scope while keeping the legacy display title.
- Added two-step confirmation for permanent Telegram message deletion.
- Added Docker build/start/health verification to GitHub Actions.

### CI status
- Early CI failures were caused by test invocation/import layout and one test-lifetime mistake, not by production media behavior.
- The workflow was made granular, those test issues were fixed, and subsequent full regression + Docker health runs are green.

### Remaining open work
Only real Telegram/browser media validation remains:
- small/large photo preview;
- small/large inline video playback;
- browser video download;
- interrupted real media transfer recovery.

A repeatable checklist is in docs/MANUAL_TESTING.md.


## 2026-09-24 — Real Telegram media validation passed

User completed the real Telegram/browser validation after implementation and reported no issues.

Validated in practice:
- photo preview;
- inline video playback;
- browser video download;
- interrupted-download recovery / re-download flow.

Result:
- Final open media-validation task is complete.
- P0, P1, P2, and P3 backlog items for the current scope are complete.
- Recent GitHub Actions runs are green, including regression tests and Docker build/health checks.
- Branch `feature/media-support` is ready for merge review.


## 2026-09-24 — Merge to main and Remember Me rerun-race fix

Merge:
- Fast-forward merged `feature/media-support` into `main`.
- No conflict and no merge commit were required.

Remember Me symptom:
- User reported that the Web login page still appeared after each application restart even though Remember Me was selected.

Re-investigation:
- Reviewed the actual `extra-streamlit-components` CookieManager Python and frontend implementations.
- Cookie writes/deletes are executed by a browser-side custom component.
- The application called `st.rerun()` immediately after `CookieManager.set(...)`.
- This could tear down the current component/render pass before the browser persisted the cookie.
- Result: current Streamlit session was authenticated, but a restart had no persistent browser cookie to restore.

Fix on `main`:
- Successful Remember Me login no longer forces an immediate `st.rerun()`.
- The current run is allowed to complete/stop so the browser component can persist the cookie and trigger its own rerun.
- Non-Remember login can still rerun immediately because it does not require a cookie write.
- Web logout similarly avoids immediate rerun after cookie deletion and uses `st.stop()` so the browser-side delete can complete.
- Added regression tests for the Remember-vs-non-Remember rerun behavior.

Validation required:
- Login once with Remember Me enabled.
- Fully stop/start the application.
- Reopen the same browser profile and application URL.
- Confirm Web login is restored automatically.


## 2026-09-24 — Product renamed to Telegram Harbor

User selected **Telegram Harbor** as the product name.

Applied on `main`:
- Added `config/branding.py` as the central product identity source.
- Streamlit browser/page title now uses Telegram Harbor.
- Login screen now shows Telegram Harbor.
- Sidebar now shows Telegram Harbor branding.
- Structured logger namespaces changed from `telegram_aranger.*` to `telegram_harbor.*`.
- Docker Compose service renamed to `telegram-harbor`.
- CI Docker image/container names renamed to `telegram-harbor`.
- Backup directory prefix changed to `telegram-harbor-backup-*`.
- README and operational docs updated to Telegram Harbor.
- `.codex` context/decisions/tasks/agent notes updated.
- Added a small branding regression test.
- GitHub Actions push workflow now targets `main` only after the media feature branch was merged.

Backward compatibility intentionally preserved:
- GitHub repository remains `majiddarvishan/telegram_aranger`.
- Existing remember-me cookie/component identifiers are retained so the rename itself does not invalidate existing browser state.
- Default database filename `telegram_manager.db` is retained so existing installations continue using the same database.
- Docker volume `telegram_data` is retained so existing persistent data is not hidden behind a new volume name.

Brand note:
- README identifies Telegram Harbor as an independent project not affiliated with or endorsed by Telegram.


## 2026-09-24 — v1.0.0 checkpoint and sticky message header

Release checkpoint:
- First formal Telegram Harbor version set to `1.0.0`.
- Added root `VERSION` file.
- `config/branding.py` exposes `PRODUCT_VERSION` from that file.
- Sidebar shows `v1.0.0`.
- README and branding tests record v1.0.0.
- Stable release checkpoint SHA: `bd8c8b211aa8e3ee5ca09c864b3e4803eac6807b`.
- CI for that checkpoint passed.

Subsequent UI change:
- User reported that the chat/search/tag/date control block scrolled away with message content.
- Root cause: Streamlit container used `key="message_header"` while CSS targeted `.st-key-message-header`, so the selector did not match the generated class.
- Container key is now `message-header` and its CSS class is `.st-key-message-header`.
- Header uses `position: sticky; top: 0` and stays in normal layout flow, so it remains visible while scrolling without hard-coding sidebar width.
- The obsolete artificial header spacer was removed.
- Added a UI regression test for key/selector/sticky behavior.


Git tag tooling note:
- No tag existed before v1.0.0.
- Intended lightweight/annotated Git tag: `v1.0.0`.
- It must point to release checkpoint `bd8c8b211aa8e3ee5ca09c864b3e4803eac6807b`, before the sticky-header change.
- The active GitHub connector exposes branch/file/ref updates but no tag-ref creation action, so the Git tag itself remains pending rather than being falsely recorded as created.


## 2026-09-25 — Fixed message header and integrated date navigation

User reported that the previous sticky-header implementation still scrolled out of view and requested moving the bottom date-navigation arrows into the same header.

Changes on `main`:
- Replaced sticky positioning with a true viewport-fixed message-control header.
- Header now uses `position: fixed` with high z-index and a dedicated layout spacer below it.
- Chat selector, message search, tag filter, date-range picker, Previous Day and Next Day controls are all in the same fixed header.
- Removed the old bottom `message_navigation` container and bottom spacer entirely.
- Previous/Next date behavior still uses the existing pending-date-range mechanism and retains the future-date guard.
- Added responsive fixed-header offsets for narrow screens and collapsed sidebar state.
- Added/updated UI regression coverage for fixed positioning and removal of the bottom navigation container.

Current development version remains `1.0.1-dev`.


## 2026-09-25 — Fixed-header clipping and collapsed-sidebar alignment

User provided a screenshot showing two layout defects after the fixed-header change:
- the top of the fixed header was hidden under Streamlit's own toolbar;
- when the sidebar was collapsed, the fixed header started too far to the right and the header's inherited width overflowed the viewport, clipping right-side controls.

Root causes:
- the fixed header used `top: 0.75rem`, placing it under Streamlit's toolbar;
- the safe/default horizontal offset assumed the expanded sidebar;
- Streamlit's keyed container retained a 100% width while fixed left/right offsets were also applied, causing horizontal overflow.

Fix:
- move the fixed header below the Streamlit toolbar with `top: 4rem`;
- make collapsed/no-sidebar the default layout with `left/right: 5rem`;
- apply `left: 26rem` only when `stSidebar[aria-expanded="true"]` exists;
- override keyed-container width with `width: auto !important` and `max-width: none !important`;
- use an opaque `var(--background-color)` background so underlying message text cannot bleed through;
- increase the layout spacer to 210px on desktop and 285px on narrow screens;
- add regression assertions for viewport width and sidebar alignment.

Current development version remains `1.0.1-dev`.


## 2026-09-25 — Opaque fixed-header backdrop

User reported that message cards still visually mixed with the fixed header while scrolling.

Cause:
- A fixed header overlays the scrolling document, so message cards still pass underneath it.
- Depending on Streamlit's internal container structure/stacking contexts, an opaque background on only the keyed container was not sufficient to fully hide underlying message content in all gaps.

Fix:
- Added a dedicated fixed `.message-header-backdrop` directly below the control header.
- The backdrop shares the same CSS variables for top/left/right/height as the header and has an opaque application background.
- Backdrop uses `pointer-events:none` and z-index 9998.
- Header uses z-index 10000, `isolation:isolate`, and an explicit opaque background.
- Streamlit internal vertical blocks inside the header also receive an opaque background.
- Header, backdrop, and spacer now share CSS variables so future layout changes stay aligned.
- Added regression assertions for the opaque backdrop and stacking behavior.

Current development version remains `1.0.1-dev`.


## 2026-09-25 — Replace fixed overlay header with dedicated message scroll area

User confirmed that multiple fixed/z-index/backdrop variants still allowed message cards to visually mix with the header while scrolling.

Final architecture change:
- Removed viewport-fixed header behavior entirely.
- Removed the opaque backdrop and artificial fixed-header spacer.
- Header now stays in normal Streamlit document flow.
- Message cards are rendered inside an official fixed-height Streamlit container with its own vertical scrolling.
- Because only the message area scrolls, messages can no longer pass behind or overlap the header.
- Previous/Next date navigation remains inside the header.
- Message scroll container uses key `message-scroll-area`.
- Current scroll height is 420px to reduce the chance that the outer page itself needs to scroll on normal desktop viewports.
- Updated UI regression coverage to ensure no fixed header/backdrop/spacer CSS returns.

This replaces the earlier fixed-overlay approach; those earlier fixes should be considered superseded.


## 2026-09-25 — v1.0.1 checkpoint and larger message panel

User confirmed the dedicated message-scroll architecture works correctly.

Release checkpoint:
- Telegram Harbor v1.0.1 metadata finalized.
- Release checkpoint SHA: `a7648e64f1cd8efc0c098b4eb0a689e6bd94d873`.
- VERSION at that checkpoint is `1.0.1`.
- README and CHANGELOG mark v1.0.1 as the latest release.
- The connector still does not expose Git tag-ref creation; the intended tag `v1.0.1` must point exactly to the checkpoint above.

Post-release development:
- Current development version moved to `1.0.2-dev`.
- Main message panel default height increased from 420px to 620px.
- Added `MESSAGE_SCROLL_HEIGHT` environment setting.
- Minimum accepted configured height is 300px.
- UI reads the scroll height from settings instead of a hard-coded UI constant.
- Added regression coverage for the default 620px setting and CI coverage for settings defaults.


## 2026-09-25 — Move Load More beside Refresh

User requested moving **Load More Messages** out of the scrollable message panel and placing it beside **Refresh Messages**.

Changes:
- `Refresh Messages` and `Load More Messages` now render together in a compact action row above the message panel.
- `Load More Messages` is shown only when the currently loaded count reaches the active result limit.
- The scrollable panel now contains only the message-count caption and message cards.
- Added regression coverage that asserts Load More belongs to the action-bar renderer and not the scroll-area renderer.
- Current message panel default remains 620px and is configurable through `MESSAGE_SCROLL_HEIGHT`.


## 2026-09-25 — v1.0.2 release checkpoint

User confirmed the updated message action layout works correctly and requested version/tag.

Release:
- VERSION set to `1.0.2`.
- Branding regression test updated to expect `1.0.2`.
- README marks `v1.0.2` as latest release.
- CHANGELOG contains a dedicated `1.0.2` section.
- Release checkpoint SHA: `9a4c429827ec4e31ef1376ae97b0b074a13dd7e9`.
- v1.0.2 includes:
  - dedicated scrollable message panel;
  - default 620px configurable message panel height;
  - `MESSAGE_SCROLL_HEIGHT` setting;
  - **Load More Messages** moved beside **Refresh Messages** outside the scroll panel.

Tag note:
- No Git tags currently exist in the repository.
- Intended tag: `v1.0.2` pointing exactly to `9a4c429827ec4e31ef1376ae97b0b074a13dd7e9`.
- The connected GitHub actions expose branch/file writes and read-only Git-ref access, but no tag-ref creation action, so tag creation remains an external/manual Git operation.


## 2026-09-25 — Windows TgCrypto warning / tgcrypto2 migration

Observed on Windows:
- Pyrogram printed: `TgCrypto is missing! Pyrogram will work the same, but at a much slower speed.`

Root cause:
- The project still depended on legacy `TgCrypto>=1.2.5`.
- Original TgCrypto is archived and its published Windows wheels do not cover modern CPython versions such as 3.14.
- Pyrogram therefore falls back to slower pure-Python crypto when the compiled `tgcrypto` module is unavailable.

Fix:
- Replaced `TgCrypto>=1.2.5` with `tgcrypto2>=1.3.6,<2`.
- `tgcrypto2` is a maintained fork and intentionally exports the same `tgcrypto` import name, so Pyrogram source code does not change.
- Added `tests/test_crypto_acceleration.py` to verify the `tgcrypto2` distribution and expected crypto functions.
- Added a dedicated Windows + Python 3.14 GitHub Actions job that installs all requirements and imports both `tgcrypto` and Pyrogram.
- README contains cleanup/reinstall commands for existing Windows virtual environments.
- Dependency policy updated to document the fork and compatibility rationale.
- Current development version moved to `1.0.3-dev`; latest release remains `v1.0.2`.


## 2026-09-25 — Remove Streamlit access from TelegramRuntime thread

Observed runtime warnings:
- `Thread 'TelegramRuntime': missing ScriptRunContext!`
- slow wait logs without an operation name, including waits around 3.3s and 37.9s.

Root cause:
- several async functions in `services/telegram_service.py` called `get_runtime()` while already running on the dedicated `TelegramRuntime` thread;
- `get_runtime()` reads `st.session_state`, which requires Streamlit's ScriptRunContext and must not run on the background Telegram thread.

Fix:
- all public synchronous service wrappers now obtain `runtime/client` on the Streamlit thread before submitting work;
- async Telegram coroutines receive the runtime/client explicitly and no longer call `get_runtime()`;
- media download coroutines also receive the Pyrogram client explicitly;
- `TelegramRuntime.run()` now accepts an `operation` label;
- slow-wait logs now include the operation name;
- added regression coverage that inspects all Telegram background coroutines and forbids `get_runtime()`, `streamlit`, or `st.session_state` access;
- updated media tests to pass fake clients directly;
- added a slow-wait logging test that verifies `operation` is present.

Based on the current UI flow, the earlier first two waits were likely session restore followed by dialog loading; new logs will confirm this explicitly.


## 2026-09-25 — v1.0.3 release checkpoint

Release:
- VERSION set to `1.0.3`.
- README and branding regression updated to v1.0.3.
- CHANGELOG finalized for Windows tgcrypto2 compatibility and TelegramRuntime ScriptRunContext fixes.
- Release checkpoint SHA: `6c27b0343f7534a2c7ff906f27483791df601fe4`.
- Intended Git tag: `v1.0.3` on exactly that SHA.


## 2026-09-25 — Reduce Telegram GetDialogs startup latency

Observed production logs on Windows showed:
- repeated `messages.GetDialogs` FloodWaits of 10–18 seconds;
- multiple near-concurrent `get_dialogs` operations taking about 63–67 seconds;
- multiple Streamlit startup/rerun passes.

Root cause:
- `render_main()` fetched all Telegram dialogs whenever session-state dialogs were empty;
- Pyrogram `get_dialogs()` was called without a limit, so it could issue multiple Telegram `messages.GetDialogs` requests;
- initial Streamlit reruns / multiple browser sessions could trigger duplicate uncached dialog fetches before session state was populated.

Fix:
- SQLite schema bumped to version 3.
- Added `telegram_dialog_cache` keyed by local Telegram account + chat.
- Normal startup first reads cached dialogs from SQLite.
- Added `TELEGRAM_DIALOG_LIMIT` with default 100.
- Pyrogram dialog retrieval now passes that explicit limit.
- Added a process-wide dialog-refresh lock; concurrent uncached sessions serialize and the later session rechecks SQLite cache before hitting Telegram.
- **Refresh Chats** is now the explicit network refresh path.
- Failed explicit refresh falls back to the existing cached list when available.
- `application_ready` is logged once per Streamlit session instead of every rerun.
- Added DB/cache/service tests, including verification that limit=100 reaches Pyrogram.
- Current development version is `1.0.4-dev`.

Expected behavior:
- first run after this upgrade may perform one bounded Telegram dialog fetch because no dialog cache exists yet;
- subsequent restarts should load the dialog list locally and should not emit `get_dialogs` slow-wait logs unless the user explicitly presses **Refresh Chats** or the cache is absent.


## 2026-09-25 — v1.0.4 release checkpoint

Release:
- VERSION set to `1.0.4`.
- README and branding regression updated to v1.0.4.
- CHANGELOG finalized for dialog-cache/startup performance improvements.
- Release checkpoint SHA: `0c3144f4d99201a917c9353c788def4df9fb4258`.
- Intended Git tag: `v1.0.4` on exactly that SHA.
- The connected GitHub tools still expose tag refs read-only; tag creation requires a local Git push.


## 2026-09-25 — GUI branch and visual design audit

User requested:
- create a dedicated `gui` branch;
- review Telegram Harbor as a professional product/visual designer;
- plan visual improvements before implementation.

Branch:
- created `gui` from `main@2bd6fbd18ac6ab03a38ee5ffc586c2d76c8ccc49`.

Audit summary:
- functionality is strong, but the interface still visually resembles a capable Streamlit admin panel rather than a fully polished product;
- primary issue is visual hierarchy, not missing functionality;
- sidebar is information-dense;
- toolbar controls have similar visual weight;
- message cards are form-heavy because tag editing and destructive actions are permanently visible;
- spacing/radius/color/typography are not governed by one design system;
- emoji currently act as an inconsistent icon system;
- auth/empty/loading/error states need a consistent product treatment;
- responsive behavior should be deliberately designed rather than only patched.

Design direction:
- clean utility / Harbor Console;
- content-first;
- calm, professional, low-decoration interface;
- subtle Telegram Harbor identity;
- semantic colors and reusable design tokens;
- avoid fragile DOM-dependent CSS where possible.

Planned phases:
1. GUI-P0 design foundation;
2. GUI-P3 message-card redesign;
3. GUI-P1 sidebar;
4. GUI-P2 toolbar/action bar;
5. GUI-P4 auth and state screens;
6. GUI-P5 responsive/accessibility;
7. GUI-P6 polish.

Why message cards are prioritized early:
- they dominate the user's working time and currently have the largest visual opportunity.

Files added/updated:
- `docs/GUI_DESIGN_PLAN_FA.md` — full Persian design audit and phased plan;
- `.codex/GUI_PLAN.md` — executable GUI backlog and guardrails;
- `.codex/START_HERE.md`, `.codex/PROJECT_CONTEXT.md`, `.codex/TASKS.md` — branch/context updates.

No production UI behavior or application code was changed during this planning step.


## 2026-09-25 — GUI-P0 design foundation implementation

Implementation started on branch `gui`.

Completed:
- added `ui/theme.py` as the single presentation-layer foundation;
- introduced semantic design tokens for spacing, radii, control height, surfaces, borders, text and semantic status colors;
- based primary visual colors on Streamlit theme variables so Light/Dark themes can inherit correctly;
- centralized the message header and message-scroll CSS previously embedded in `ui/main.py`;
- applied the theme globally from `app.py`;
- standardized baseline form, button, input, alert, sidebar, caption and divider styling;
- added focus-visible treatment for keyboard accessibility;
- added reduced-motion support;
- added safe reusable HTML helpers for status badges and section titles;
- preserved the existing normal-flow message header + dedicated scroll-container architecture;
- added `tests/test_theme.py`;
- enabled GitHub Actions push validation for the `gui` branch and added a dedicated theme-foundation test step.

Still open:
- manual Light/Dark visual inspection is required before closing GUI-P0.

No Telegram, database, authentication, dialog-cache, message-history, tag or media behavior was changed.
