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


## Manual validation runner

Use `scripts/youtube_manual_validate.py` for repeatable service-level live checks. The script is intentionally excluded from CI execution; its own unit tests are offline.

It does not persist the original YouTube URL, thumbnails, signed media URLs, cookies or browser/authentication state in the JSON report.

### Inspect only

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode inspect \
  --report-file validation-reports/inspect.json
```

Inspect output shows normalized metadata, format count, subtitle/caption tracks, policy state and FFmpeg capability without downloading media.

### Video + Audio

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode video_audio \
  --quality max_720p \
  --save-directory "/absolute/path/to/output" \
  --acknowledge \
  --report-file validation-reports/video-720p.json
```

### Audio only

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode audio_only \
  --save-directory "/absolute/path/to/output" \
  --acknowledge \
  --report-file validation-reports/audio.json
```

### Manual subtitle

First run Inspect and choose a track reported with `source=manual`, then:

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode video_audio \
  --quality max_720p \
  --save-directory "/absolute/path/to/output" \
  --subtitle-language en \
  --subtitle-source manual \
  --acknowledge \
  --report-file validation-reports/manual-subtitle.json
```

### Auto-generated caption

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode video_audio \
  --quality max_720p \
  --save-directory "/absolute/path/to/output" \
  --subtitle-language en \
  --subtitle-source automatic \
  --acknowledge \
  --report-file validation-reports/auto-caption.json
```

### Explicit directory creation

A missing output directory is not created unless explicitly requested:

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode audio_only \
  --save-directory "/absolute/path/new-output" \
  --create-directory \
  --acknowledge
```

### Allowed-root validation

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode video_audio \
  --save-directory "/srv/telegram-harbor/youtube/test" \
  --allowed-root "/srv/telegram-harbor/youtube" \
  --create-directory \
  --acknowledge
```

Repeat `--allowed-root` for multiple configured roots.

### Windows PowerShell

```powershell
python scripts/youtube_manual_validate.py `
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" `
  --mode video_audio `
  --quality max_720p `
  --save-directory "C:\Users\Majid\Downloads\TelegramHarbor" `
  --acknowledge `
  --report-file "validation-reports\windows-video.json"
```

Before the Windows live download:

```powershell
ffmpeg -version
ffprobe -version
```

### Docker

Build the image with the exact source commit embedded:

```bash
docker build \
  --build-arg TELEGRAM_HARBOR_BUILD_SHA="$(git rev-parse HEAD)" \
  -t telegram-harbor:test .
```

Then run the validation:

```bash
docker run --rm \
  -v telegram_youtube_validation:/data/youtube \
  --entrypoint python \
  telegram-harbor:test \
  scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode video_audio \
  --quality max_720p \
  --save-directory /data/youtube \
  --allowed-root /data/youtube \
  --acknowledge
```

The validation script does not load Telegram settings, so Telegram credentials are not required for this service-level Docker validation.

## Collision validation procedure

To verify grouped collision behavior with a real output:
1. complete one media + subtitle download;
2. keep both files in the Save directory;
3. run the same command again;
4. confirm the second media and subtitle both receive the same numeric suffix, for example:
   - `Example (2).mp4`
   - `Example (2).srt`
5. record both filenames in the validation evidence.

Do not delete/rename the first pair until the second run has completed.


## Release-readiness automated hardening

The following code-level checks have been completed while manual/live acceptance remains open:

- confirmed YouTube workspace routing is not blocked by missing/disconnected Telegram account state;
- added responsive container keys and design-system rules for metadata, thumbnail and output controls;
- narrow layout now structurally collapses YouTube metadata/output controls to full-width columns;
- YouTube UI continues to inherit adaptive Light/Dark design tokens and does not introduce a fixed light-only surface;
- unknown downloader exceptions are normalized to a generic safe message;
- unexpected UI exceptions no longer expose raw exception text;
- validation-runner unexpected failures expose only a generic message plus exception type;
- regression tests include synthetic signed/query-token strings and assert they do not reach user-visible/report output;
- rights/service notice and stronger restriction warnings are rendered before the acknowledgement control;
- blocked content does not present a meaningless acknowledgement path.

These are automated/code-review findings only. They do not complete the manual Light/Dark/narrow screenshot review or any live YouTube download case.


## Post-download report checks

For download modes, `scripts/youtube_manual_validate.py` now adds a `checks` object to the JSON report and returns a non-zero exit code if the checks fail.

Checks include:
- final media file exists;
- final media remains under the selected Save directory;
- completion progress event was observed;
- when subtitle/caption is enabled:
  - subtitle file exists;
  - subtitle remains under the selected Save directory;
  - media and subtitle have exactly the same basename.

This makes the manual evidence self-validating for the matched-basename and final-path parts of YT-P7. Collision validation still requires a second real run with the first output pair left in place.


## Environment/build identity evidence

Every manual-runner JSON report records a safe environment summary:
- operating-system family;
- OS release;
- CPU architecture;
- Python version;
- whether the runner detected Docker;
- Telegram Harbor `VERSION`;
- source commit SHA when available.

The report deliberately does **not** record hostname, username, environment variables, credentials or network-interface identity.

Native source-tree runs resolve the current commit from Git when available.

Docker images accept:

`TELEGRAM_HARBOR_BUILD_SHA`

as a build argument/environment value. For release validation, always build with:

```bash
docker build \
  --build-arg TELEGRAM_HARBOR_BUILD_SHA="$(git rev-parse HEAD)" \
  -t telegram-harbor:test .
```

For Docker Compose, export the same value before building:

```bash
export TELEGRAM_HARBOR_BUILD_SHA="$(git rev-parse HEAD)"
docker compose build
```

This ensures the validation report can be tied back to the exact source commit rather than only to an image tag.
