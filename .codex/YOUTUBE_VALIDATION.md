# YouTube V1 Validation Matrix

Branch: `feature/youtube-download`
Validation start HEAD: `27c468c5285b41fd42dd8eaa6573bdf007d74600`
GitHub Actions run: `36191266353`

## Rule

This file separates automated evidence from manual/live acceptance.

Do not mark a YT-P7 manual item complete merely because a fake/offline unit test covers the same behavior. Live YouTube, native Windows, Docker runtime and browser/visual checks remain manual until they are actually performed.

CI must remain free of live YouTube calls.

## Automated validation already passing

At the validation-start HEAD, GitHub Actions completed successfully for:

- `unittest`
  - YouTube service tests;
  - download-path safety tests;
  - warning/policy tests;
  - download-engine tests with fake downloader behavior;
  - YouTube UI smoke/formatting tests;
  - existing Telegram Harbor regression tests.
- `windows-python314`
  - dependency installation;
  - crypto acceleration;
  - native Windows YouTube path tests.
- `docker-build`
  - image build;
  - `ffmpeg` availability;
  - `ffprobe` availability;
  - Streamlit container startup;
  - Streamlit health endpoint.

Automated tests already exercise, without live YouTube network calls:

- public-video URL validation shapes;
- metadata/format/subtitle normalization;
- Manual vs Auto-generated subtitle classification;
- warning/acknowledgement policy;
- blocked DRM/private/member/auth-style states from normalized metadata/errors;
- save-directory validation and allowed-root containment;
- Windows/Linux filename sanitation;
- title-based output naming;
- media/subtitle matched basenames;
- grouped collision suffixing;
- Video + Audio option generation;
- Audio-only option generation;
- quality preset mapping;
- SRT preference and truthful VTT/original fallback;
- progress normalization;
- cleanup/error mapping;
- independent Streamlit workspace wiring.

These are regression evidence, not substitutes for YT-P7 live/manual acceptance.

## Manual/live validation status

### UI visual review — YT-P5 remainder
- [ ] Light theme.
- [ ] Dark theme.
- [ ] Narrow/responsive layout.
- [ ] Confirm YouTube workspace does not visually interfere with Telegram Messages workspace.

### YT-P7
- [ ] Inspect a currently accessible public test video through the real Streamlit UI.
- [ ] Live Video + Audio download.
- [ ] Live Audio-only download.
- [ ] Live Manual subtitle download.
- [ ] Live Auto-generated caption download.
- [ ] Confirm media/subtitle final files share exactly the same basename.
- [ ] Confirm a real output collision applies one suffix to the complete output group.
- [ ] Confirm Save-directory create/validate/write behavior through the UI.
- [ ] Native Windows path + FFmpeg/FFprobe + real download.
- [ ] Docker real download using `/data/youtube`.
- [ ] Confirm ordinary public-content warning is non-blocking after explicit acknowledgement.
- [ ] Confirm representative invalid/unavailable/restricted error presentation without bypass behavior.
- [ ] Final merge/release review.

## Suggested live media candidate

For the basic public-video smoke test, a small video that the tester has permission to save should be used.

One commonly used downloader test ID is:

`BaW_jenozKc`

Before validation, confirm it is still publicly accessible and appropriate to use. Do not add this or any other live URL to CI.

For manual/auto subtitle cases, use public videos where the tester has permission to save the media/captions and where the required track type is visibly reported by Inspect.

## Evidence to record for each manual case

Record:
- date/time;
- environment: native Linux / native Windows / Docker;
- app branch + commit SHA;
- video ID only (avoid unnecessary full URL query parameters);
- selected mode/quality;
- subtitle language/type if used;
- Save directory;
- final media filename;
- final subtitle filename/format if used;
- whether progress/post-processing was visible;
- pass/fail plus concise failure detail.

Do not record cookies, auth headers, browser session data, Telegram secrets, downloader temporary tokens or signed media URLs.
