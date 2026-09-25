# YouTube Download Feature Plan

Branch: `feature/youtube-download`
Baseline: `main@ff7422284c7850ece9f3db9816cf600ff911a560`

Status: implementation active. YT-P1 service foundation is complete; YT-P2 filesystem safety is next.

Primary Persian design document:
`docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`

## Confirmed user requirements

- Add YouTube download capability to Telegram Harbor.
- Ask the user for the save location.
- Support optional subtitle download.
- Keep the saved media filename based on the sanitized YouTube video title.
- When a subtitle is downloaded, keep the same basename as the media file.
- Show copyright / service-restriction warnings when applicable.
- Warning is informational/acknowledgement-oriented and should not block ordinarily accessible public content.
- Do not bypass DRM, paywalls, private/member-only access controls, or similar protection mechanisms.
- Do not implement code until the planning/task phase is approved.

## V1 scope

- Single public YouTube video URL.
- Inspect metadata before download.
- Video + audio output.
- Audio-only output.
- Optional single subtitle track download.
- Manual subtitles and auto-generated captions are identified separately.
- Default subtitle output target is SRT; fallback format must be reported when conversion is unavailable.
- Simple quality presets.
- User-supplied save directory.
- Title-based matched output naming.
- Progress and post-processing state.
- Warning / acknowledgement flow.
- Windows + Linux path handling.
- Docker/FFmpeg support.
- No live YouTube dependency in CI.

## Save-location decision

V1 uses a required filesystem path field.

Important:
- On a local installation, this is the user's local machine path.
- On a remotely hosted installation, this is a path on the host running Telegram Harbor.
- UI must state this explicitly.
- A browser-native directory picker is deferred because Streamlit does not provide one as a stable built-in abstraction for arbitrary local filesystem write access.

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
- No cookies/authentication import in V1.
- No automatic reuse of the Telegram SOCKS5 proxy.
- No playlist/channel/batch download in V1.
- No production code in this planning commit set.

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
- [ ] Require Save directory input.
- [ ] Normalize/resolve path.
- [ ] Verify directory existence/writability.
- [ ] Decide/create directory only with explicit user intent.
- [ ] Sanitize the YouTube title into the shared output basename.
- [ ] Save media as `<sanitized-title>.<media-ext>`.
- [ ] Save a selected subtitle as `<sanitized-title>.<subtitle-ext>`.
- [ ] Prevent output path escape.
- [ ] Handle filename collisions as one output group so media/subtitle basenames remain aligned.
- [ ] Add optional allowed-root configuration for hosted mode.
- [ ] Cover Windows/Linux path cases.

### YT-P3 — Warning and acknowledgement
- [ ] General rights/service notice.
- [ ] Restriction signal model.
- [ ] Explicit acknowledgement state.
- [ ] Keep warning non-blocking for normally accessible public content.
- [ ] Do not bypass access controls.
- [ ] Tests for warning states.

### YT-P4 — Download engine
- [ ] Video + audio.
- [ ] Audio only.
- [ ] Quality presets.
- [ ] Optional subtitle-track download.
- [ ] Prefer SRT output for the selected subtitle; report VTT/original fallback explicitly.
- [ ] Keep manual subtitle vs auto-caption provenance in result metadata.
- [ ] Progress normalization.
- [ ] FFmpeg/post-process state.
- [ ] Partial-file cleanup/recovery.
- [ ] Final output path reporting.
- [ ] Failure handling.

### YT-P5 — Streamlit UI
- [ ] Independent YouTube workspace.
- [ ] URL input + Inspect action.
- [ ] Metadata/thumbnail preview.
- [ ] Mode/quality controls.
- [ ] Subtitle enable/disable control.
- [ ] Subtitle language selector with Manual / Auto-generated labeling.
- [ ] Subtitle format display/selection according to supported V1 behavior.
- [ ] Save directory input.
- [ ] Warning/acknowledgement UI.
- [ ] Download progress.
- [ ] Completed/error state.
- [ ] Light/Dark/responsive behavior.

### YT-P6 — Platform/docs
- [ ] Windows FFmpeg setup.
- [ ] Docker FFmpeg setup.
- [ ] Deployment documentation.
- [ ] README update.
- [ ] Manual testing checklist.
- [ ] CI without live YouTube calls.

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
- [ ] Merge/release review.

## Deferred

- playlists;
- channels;
- browser cookies;
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

- Branch is `feature/youtube-download`.
- Implementation is active on this branch after explicit user approval.
- YT-P1 is complete; continue from YT-P2 unless the user changes priority.
- Read this file and `docs/YOUTUBE_DOWNLOAD_PLAN_FA.md` before proposing changes.
- Preserve existing Telegram Harbor behavior and architecture.
- Continue implementation phase-by-phase from the next incomplete YouTube phase.
- Keep each YouTube phase separately reviewable and update `.codex/TASKS.md` / `.codex/SESSION.md` as work progresses.
- Do not merge to `main` unless the user explicitly asks.
