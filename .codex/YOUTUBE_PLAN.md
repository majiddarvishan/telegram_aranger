# YouTube Download Feature Plan

Branch: `feature/youtube-download`
Baseline: `main@ff7422284c7850ece9f3db9816cf600ff911a560`

Status: planning only. No implementation code has been added in this phase.

Primary Persian design document:
`docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`

## Confirmed user requirements

- Add YouTube download capability to Telegram Harbor.
- Ask the user for the save location.
- Show copyright / service-restriction warnings when applicable.
- Warning is informational/acknowledgement-oriented and should not block ordinarily accessible public content.
- Do not bypass DRM, paywalls, private/member-only access controls, or similar protection mechanisms.
- Do not implement code until the planning/task phase is approved.

## V1 scope

- Single public YouTube video URL.
- Inspect metadata before download.
- Video + audio output.
- Audio-only output.
- Simple quality presets.
- User-supplied save directory.
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
- [x] Create implementation backlog.

### YT-P1 — Service foundation
- [ ] Add downloader dependency behind a service abstraction.
- [ ] Detect FFmpeg capability.
- [ ] Validate supported YouTube URLs.
- [ ] Inspect metadata without downloading media.
- [ ] Normalize formats/quality presets.
- [ ] Normalize downloader errors.
- [ ] Add unit tests.

### YT-P2 — Filesystem safety
- [ ] Require Save directory input.
- [ ] Normalize/resolve path.
- [ ] Verify directory existence/writability.
- [ ] Decide/create directory only with explicit user intent.
- [ ] Sanitize filenames.
- [ ] Prevent output path escape.
- [ ] Handle filename collisions.
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
- subtitles;
- chapters;
- SponsorBlock.
