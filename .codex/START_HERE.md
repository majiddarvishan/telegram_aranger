# START HERE

## Repository / source of truth
- Product: **YARA — Your Archive & Retrieval Assistant**
- Repository: `majiddarvishan/yara`
- Source-of-truth branch: `main`
- Current main HEAD at this handoff: `0934e67401e078bc57f0f4acddffd1f72bf6a768`
- Merge commit: `Merge feature/youtube-download into main`
- Former feature branch `feature/youtube-download` is already merged and is behind `main`; do not continue new work on it.
- Latest confirmed CI on the merged/rename line is green. Re-check HEAD and Actions before editing because the repository may advance after this handoff.

## Product identity
YARA is the new permanent product name.

Expansion:
**YARA = Your Archive & Retrieval Assistant**

Repository rename is complete:
- old: `majiddarvishan/telegram_aranger`
- current: `majiddarvishan/yara`

Persisted compatibility identifiers may still intentionally contain older names (for example existing database/preferences/build env identifiers) when changing them would break existing installations. Do not rename persisted identifiers blindly.

## Logo decision
The user selected the dark YARA artwork with:
- central circular YARA wordmark;
- Persian `یارا`;
- dark navy/black background;
- cyan/purple circuit/network accents.

The image was supplied in ChatGPT and is the approved visual logo.

Important status:
- repository/product rename is complete;
- the selected binary logo is **not present in the Git tree at this handoff**;
- GitHub repository Social Preview / repository image still needs the approved image to be uploaded through GitHub UI or another binary-capable workflow;
- the current GitHub connector can edit UTF-8 repository files but cannot upload this binary image or mutate GitHub Social Preview settings.
Do not invent a different logo. Reuse the user-approved artwork if the user supplies/accesses it again.

## Current major capabilities
### Telegram
- local Web authentication + Remember Me;
- multiple Telegram accounts per Web user;
- encrypted Pyrogram session storage;
- Saved Messages/private/group/supergroup/channel browsing;
- cached dialogs + persisted peer metadata;
- date-range history + Load More;
- local search and chat-scoped tags;
- delete confirmation;
- photo preview;
- inline video/video-note/animation/audio/voice playback;
- browser media download and interrupted-download recovery;
- shared SOCKS5 proxy;
- SQLite persistence, migrations, backup/restore;
- Docker/Compose and GitHub Actions.

### YouTube
YouTube is an independent workspace and the feature has been merged into `main`.

Implemented:
- Inspect before download;
- normalized metadata/formats/subtitles;
- yt-dlp service abstraction;
- FFmpeg/FFprobe integration;
- Deno-compatible JavaScript challenge solving (Deno is required/recommended for the current YouTube flow on Windows);
- optional Browser Session auth;
- validated youtube.com-only Netscape `cookies.txt` fallback;
- one shared Sidebar SOCKS5 configuration for Telegram + YouTube;
- video+audio, audio-only, subtitle-only;
- exact per-format download actions;
- subtitle language selection inside the per-row Download menu;
- cancellable background download job;
- title-based non-overwriting output names;
- Save-directory validation, native folder picker and remembered path;
- normalized progress, errors and policy/rights acknowledgement.

## Recent YouTube UX fixes that require manual re-check
Automated tests are green, but these specific items came from real Windows/UI feedback and should be manually re-verified before release:

1. **Shared SOCKS5 defaults**
   - one proxy control in Sidebar for Telegram + YouTube;
   - when enabled and values are empty/invalid, visible defaults must be `127.0.0.1` and `1080`.
2. **Save-directory Browse**
   - must not raise `StreamlitWidgetAlreadyInstantiatedError`;
   - selected folder is applied on the next rerun using pending state;
   - default is the OS user's Downloads folder;
   - changed path persists across restart.
3. **Inspect stale error**
   - a previous `YouTube URL is required`/Inspect error must clear when a new Inspect starts or URL changes;
   - old error must not remain under a successful/new inspection.
4. **Formats table**
   - do not truncate formats (no `formats[:40]`);
   - video formats must remain visible;
   - column header remains outside the scrollable rows so it stays visible while scrolling;
   - each row has one `Download` popover/menu.
5. **Per-row actions**
   - menu contains `Video + Audio`, `Audio`, and `Subtitle`;
   - invalid actions are disabled for that row;
   - Subtitle offers language selection inside the menu before download.
6. **Removed redundant controls**
   - no standalone subtitle/caption metadata table in the main flow;
   - no global Output radio / Quality dropdown / global subtitle checkbox / global Download button.
7. **Cancel download**
   - active download exposes Cancel;
   - cancellation should stop safely and clean partial job state.
8. **Streamlit API cleanup**
   - touched UI uses `width="stretch"` / `width="content"` instead of deprecated `use_container_width`.

## YouTube environment learned from live Windows testing
Known working local stack during validation:
- Windows 11;
- Python 3.14.7;
- yt-dlp stable 2026.08.19;
- FFmpeg/FFprobe 9.0.2;
- Deno 2.9.7;
- SOCKS5 example `127.0.0.1:1080`;
- authenticated YouTube account cookies via `cookies.txt` worked with yt-dlp once Deno was available.

Chrome Browser Session on Windows hit Chromium cookie-encryption issues:
- first cookie DB lock;
- then `Failed to decrypt with DPAPI` / App-Bound encryption.
Therefore do not assume Chrome browser-cookie extraction is reliable on current Windows Chromium versions. `cookies.txt` remains an important fallback.

## Read order in a new session
1. `.codex/START_HERE.md`
2. `.codex/NEXT_CHAT_PROMPT.md`
3. `.codex/PROJECT_CONTEXT.md`
4. `.codex/DECISIONS.md`
5. `.codex/TASKS.md`
6. `.codex/SESSION.md`
7. `.codex/YOUTUBE_PLAN.md`
8. `.codex/YOUTUBE_VALIDATION.md`
9. `docs/MANUAL_TESTING.md`

## Rules for future work
- Start from current `main`; re-fetch HEAD first.
- Do **not** use the already-merged `feature/youtube-download` as the base for new work.
- For code changes, create a fresh branch from current `main` unless the user explicitly says to work directly on main.
- Never merge to `main` unless the user explicitly requests it.
- Keep YouTube behind the service abstraction; UI must not import yt-dlp directly.
- Keep Telegram and YouTube on one shared Sidebar SOCKS5 configuration.
- Do not persist proxy passwords or YouTube cookie contents.
- Do not implement DRM/paywall/private/member access-control bypass.
- CI must remain free of live YouTube network calls.
- Do not mark live/manual acceptance complete from CI alone.
- Update `.codex/TASKS.md` and `.codex/SESSION.md` after meaningful work.
