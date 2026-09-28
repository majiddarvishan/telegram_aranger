# YouTube Download Feature Plan

Source of truth: `main`

Status: the YouTube feature has been implemented and merged into `main`. The former `feature/youtube-download` branch is already merged and must not be used as the base for new work. Re-check current `main` HEAD and CI before edits. Remaining work is manual/live UX acceptance and any defects found there.

Primary Persian design document:
`docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`

Validation matrix: `.codex/YOUTUBE_VALIDATION.md`

Merged checkpoint before handoff-doc updates: `main@0934e67401e078bc57f0f4acddffd1f72bf6a768`. Re-check current main because documentation commits may be newer.

## Confirmed user requirements

- Add YouTube download capability to YARA.
- Ask the user for the save location.
- Support optional subtitle download.
- Keep the saved media filename based on the sanitized YouTube video title.
- When a subtitle is downloaded, keep the same basename as the media file.
- Show copyright / service-restriction warnings when applicable.
- Warning is informational/acknowledgement-oriented and should not block ordinarily accessible public content.
- Do not bypass DRM, paywalls, private/member-only access controls, or similar protection mechanisms.
- Implementation was explicitly approved by the user; continue only from remaining incomplete validation/review work.

## V1 scope

- Single public YouTube video URL.
- Inspect metadata before download.
- Video + audio output.
- Audio-only output.
- Optional single subtitle track download.
- Manual subtitles and auto-generated captions are identified separately.
- Default subtitle output target is SRT; fallback format must be reported when conversion is unavailable.
- Simple quality presets.
- Save directory defaults to the local user's Downloads folder, supports native Browse on local installs, and remembers the last selected path.
- Title-based matched output naming.
- Progress and post-processing state.
- Warning / acknowledgement flow.
- Windows + Linux path handling.
- Docker/FFmpeg support.
- No live YouTube dependency in CI.

## Save-location decision

V1 uses a host filesystem path field with a sensible local default (`Downloads`). The user may type a path or use the native folder picker on local installs.

Important:
- On a local installation, this is the user's local machine path.
- On a remotely hosted installation, this is a path on the host running YARA.
- UI must state this explicitly.
- A local native directory picker is implemented via the host OS dialog; remote/headless deployments retain the manual path field.

Hosted deployments should support configured allowed roots so a Web user cannot write to arbitrary server locations.

## Content-warning decision

The application cannot reliably make a legal determination about copyright ownership from YouTube metadata.

V1 behavior:
- always show a concise rights/service notice before download;
- surface stronger warning signals when metadata/downloader reports restrictions;
- require acknowledgement before starting;
- allow the user to continue for ordinarily accessible public content;
- do not add mechanisms that bypass technical access controls.

## Architecture guardrails

- YouTube functionality must live behind a service layer.
- Streamlit UI must not call the downloader library directly.
- Telegram runtime/Pyrogram code must remain independent.
- Existing Telegram media cache must not be silently reused for YouTube downloads.
- Save-path handling must be isolated in filesystem utilities.
- Support optional authenticated YouTube sessions.
- Prefer local browser-session cookies when YARA and the browser run on the same host/user.
- Keep a youtube.com-only `cookies.txt` fallback for Docker/remote deployments.
- Use one shared Sidebar SOCKS5 configuration for both Telegram and YouTube.
- Do not render a duplicate YouTube proxy panel.
- Do not collect Google username/password or use YouTube OAuth.
- No playlist/channel/batch download in V1.
- Production implementation is now present on `feature/youtube-download`; preserve the service/UI boundary and completed phase behavior.

## Planned modules

Likely implementation shape:

- `services/youtube_service.py`
- `ui/youtube.py`
- `utils/download_paths.py`
- settings additions in `config/settings.py`
- tests under `tests/`

Names may change during implementation if the existing project structure suggests a cleaner fit.

## Phases

### YT-P0 — Planning
- [x] Create isolated feature branch.
- [x] Define V1 scope.
- [x] Define save-location semantics.
- [x] Define warning semantics.
- [x] Define access-control/DRM boundary.
- [x] Define service/UI separation.
- [x] Record FFmpeg requirement.
- [x] Include optional subtitle download in V1.
- [x] Define title-based matched filename policy for media + subtitle outputs.
- [x] Create implementation backlog.

### YT-P1 — Service foundation
- [x] Add downloader dependency behind a service abstraction.
- [x] Detect FFmpeg capability.
- [x] Validate supported YouTube URLs.
- [x] Inspect metadata without downloading media.
- [x] Inspect manual subtitle and auto-caption tracks without downloading them.
- [x] Normalize subtitle language/type/format information.
- [x] Normalize formats/quality presets.
- [x] Normalize downloader errors.
- [x] Add unit tests.

### YT-P2 — Filesystem safety
- [x] Require Save directory input.
- [x] Normalize/resolve path.
- [x] Verify directory existence/writability.
- [x] Decide/create directory only with explicit user intent.
- [x] Sanitize the YouTube title into the shared output basename.
- [x] Save media as `<sanitized-title>.<media-ext>`.
- [x] Save a selected subtitle as `<sanitized-title>.<subtitle-ext>`.
- [x] Prevent output path escape.
- [x] Handle filename collisions as one output group so media/subtitle basenames remain aligned.
- [x] Add optional allowed-root configuration for hosted mode.
- [x] Cover Windows/Linux path cases.

### YT-P3 — Warning and acknowledgement
- [x] General rights/service notice.
- [x] Restriction signal model.
- [x] Explicit acknowledgement state.
- [x] Keep warning non-blocking for normally accessible public content.
- [x] Do not bypass access controls.
- [x] Tests for warning states.

### YT-P4 — Download engine
- [x] Shared Sidebar SOCKS5 proxy for Telegram and YouTube Inspect/Download.
- [x] Optional authenticated session for Inspect and Download, preferring local Browser Session with `cookies.txt` fallback.
- [x] Video + audio.
- [x] Audio only.
- [x] Quality presets.
- [x] Optional subtitle-track download.
- [x] Prefer SRT output for the selected subtitle; report VTT/original fallback explicitly.
- [x] Keep manual subtitle vs auto-caption provenance in result metadata.
- [x] Progress normalization.
- [x] FFmpeg/post-process state.
- [x] Partial-file cleanup/recovery.
- [x] Final output path reporting.
- [x] Failure handling.

### YT-P5 — Streamlit UI
- [x] Independent YouTube workspace.
- [x] URL input + Inspect action.
- [x] Metadata/thumbnail preview.
- [x] Complete per-format table with one Download menu per row.
- [x] Per-row Video + Audio / Audio / Subtitle actions.
- [x] Subtitle language selection inside the row Download menu with Manual / Auto-generated labeling.
- [x] Remove redundant global Output/Quality/subtitle controls after user review.
- [x] Save directory input.
- [x] Warning/acknowledgement UI.
- [x] Download progress.
- [x] Completed/error state.
- [ ] Light/Dark/responsive behavior.
  - [x] Responsive structure is implemented and regression-tested.
  - [ ] Manual Light/Dark/narrow screenshot review remains required.

### YT-P6 — Platform/docs
- [x] Windows FFmpeg setup.
- [x] Docker FFmpeg setup.
- [x] Deployment documentation.
- [x] README update.
- [x] Manual testing checklist.
- [x] CI without live YouTube calls.

### YT-P7 — Manual validation
- [ ] Public test video.
- [ ] Video + audio.
- [ ] Audio only.
- [ ] Manual subtitle download.
- [ ] Auto-generated caption download.
- [ ] Verify media and subtitle share the same basename.
- [ ] Verify collision suffix is applied consistently to the complete output set.
- [ ] Save directory.
- [ ] Windows path.
- [ ] Docker.
- [ ] Warning flow.
- [ ] Error scenarios.
- [x] Merge YouTube feature into `main`.
- [ ] Final manual/live release acceptance.

## Deferred

- playlists;
- channels;
- private/member-only content;
- DRM/protection bypass;
- geo-bypass;
- batch queues;
- scheduled downloads;
- multiple subtitle languages in one download job;
- advanced subtitle management beyond the single selected track;
- chapters;
- SponsorBlock.


## New-chat continuation contract

When continuing this feature in another ChatGPT conversation:

- Source of truth is `main`; the old `feature/youtube-download` branch is already merged.
- For new code work, create a fresh branch from current main unless the user explicitly requests direct-main changes.
- YT-P1 through YT-P6 are implemented and merged; do not re-implement them. Continue from manual/live validation or defects exposed by it.
- Read this file and `docs/YOUTUBE_DOWNLOAD_PLAN_FA.md` before proposing changes.
- Preserve existing YARA behavior and architecture.
- Continue implementation phase-by-phase from the next incomplete YouTube phase.
- Keep each YouTube phase separately reviewable and update `.codex/TASKS.md` / `.codex/SESSION.md` as work progresses.
- Do not merge to `main` unless the user explicitly asks.
