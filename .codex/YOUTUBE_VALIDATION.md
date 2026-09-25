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

For the basic public-video smoke test, use a small video with a documented reuse license when possible.

The old downloader test ID `BaW_jenozKc` is no longer suitable for YT-P7. yt-dlp issue #12263 documents that the video became unavailable, so it must not be used as the acceptance candidate.

Current preferred smoke-test candidate:

- Video ID: `w2S5Ov-7Mzo`
- Title: `Open Culture Voices Vlog Series "Introduction"`
- Source/uploader: Creative Commons
- Historical license evidence: Wikimedia Commons records the YouTube source as released under Creative Commons Attribution 3.0.
- Duration in the archived Commons copy: about 2 minutes 13 seconds.

Use:

`https://www.youtube.com/watch?v=w2S5Ov-7Mzo`

Runtime accessibility must still be confirmed by Telegram Harbor Inspect at test time. Do not add this or any other live URL to CI.

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

Use `scripts/youtube_manual_validate.py` for repeatable validation. CI may execute **preflight only**; CI never supplies a YouTube URL and never performs a live YouTube request. Download/Inspect scenarios remain manual/live.

### Offline preflight

Validate FFmpeg/FFprobe plus Save-directory/allowed-root behavior without contacting YouTube:

```bash
python scripts/youtube_manual_validate.py \
  --mode preflight \
  --save-directory "/absolute/path/to/output" \
  --allowed-root "/absolute/path/to"
```

A successful preflight produces a JSON report with environment/build identity, validated Save directory, FFmpeg/FFprobe discovery, and executable runtime checks. It requires `ffmpeg_runtime_ready=true`, which means both `ffmpeg -version` and `ffprobe -version` completed successfully.

For live modes it does not persist the original YouTube URL, thumbnails, signed media URLs, cookies or browser/authentication state in the JSON report. Invalid URLs are returned as structured failure reports rather than uncaught tracebacks.

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
3. run the same command again and add `--expect-collision`;
4. the runner must report `collision_expectation_met=true` and a numeric `collision_number` of 2 or greater;
5. confirm the second media and subtitle both receive the same numeric suffix, for example:
   - `Example (2).mp4`
   - `Example (2).srt`
6. record both filenames in the validation evidence.

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
- final media file exists and is a non-empty file;
- final media remains under the selected Save directory;
- completion progress event was observed;
- output basename is derived from the sanitized video title, allowing only the defined numeric collision suffix;
- media extension matches the requested mode (.mp4 or .mp3);
- when subtitle/caption is enabled:
  - subtitle file exists and is non-empty;
  - subtitle remains under the selected Save directory;
  - media and subtitle have exactly the same basename;
  - subtitle source matches Manual vs Auto-generated selection;
  - subtitle language matches the selected language;
  - subtitle extension matches the actual reported output format;
- when `--expect-collision` is supplied, a numeric collision suffix such as `(2)` is mandatory.

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


## Validation report summary

After collecting manual/live reports, summarize them offline:

```bash
python scripts/youtube_validation_summary.py validation-reports/*.json
```

To require all core runner scenarios:

```bash
python scripts/youtube_validation_summary.py \
  --require-core \
  validation-reports/*.json
```

For the stricter pre-release runner evidence gate:

```bash
python scripts/youtube_validation_summary.py \
  --require-release-ready \
  validation-reports/*.json
```

The release-ready gate additionally requires:
- native Windows live-download evidence;
- Docker live-download evidence;
- a successful acknowledged ordinary-public download;
- at least one structured failure report;
- every loaded report to carry the same concrete source commit SHA.

It still does not replace the manual Light/Dark/narrow and real Streamlit presentation review.

The summary reports runner evidence for:
- preflight;
- public Inspect;
- Video + Audio;
- Audio-only;
- Manual subtitle;
- Auto-generated caption;
- intentional collision second run;
- live Save-directory containment;
- native Windows live download;
- Docker live download;
- public acknowledged download;
- at least one structured failure report.

It also reports whether the evidence comes from one source commit or mixed commits.

The aggregator does **not** mark visual/manual-only items complete. Light/Dark/narrow review, real Streamlit warning/error presentation, and final merge/release review remain separate manual acceptance items.


### Zero-byte output rule

A file path existing on disk is not sufficient evidence of a successful download.

YT-P7 validation now requires:
- final media size > 0 bytes;
- requested subtitle/caption size > 0 bytes.

The download engine rejects zero-byte media/subtitle outputs before final acceptance. A zero-byte SRT created by FFmpeg is not treated as a successful conversion; Telegram Harbor falls back to the original non-empty subtitle format instead.


### Canonical YouTube URL boundary

Accepted public video URL shapes are reduced to one canonical form before Inspect or Download reaches the downloader:

`https://www.youtube.com/watch?v=<VIDEO_ID>`

This strips incidental share/tracking/playlist query parameters and URL fragments from the downloader request.

V1 also rejects YouTube URLs containing embedded username/password userinfo or an explicit TCP port.

The original user URL continues to stay out of validation reports; only the normalized video ID is retained.


### Release-evidence fail-closed rules

The validation summary distinguishes native Windows evidence from container evidence:
- `windows_live_download` requires `platform=Windows` **and** `docker=false`;
- Docker evidence is tracked separately with `docker=true`.

If any supplied validation report cannot be read/parsed, the summary sets:
- `report_set_readable=false`;
- `release_runner_evidence_ready=false`.

A non-zero CLI exit code alone is not the only signal; the JSON readiness field is also forced false.


### Runner evidence is not full release acceptance

Even when `--require-release-ready` succeeds, that command means the **manual-runner evidence set** is complete and internally consistent.

The JSON summary intentionally keeps:
- `manual_acceptance_required=true`;
- `full_release_ready=false`.

The following still require actual Streamlit/manual acceptance:
- public Inspect in the real UI;
- Video + Audio progress/completion UI;
- Audio-only progress/completion UI;
- Save-directory create/validate/write behavior in the real UI;
- Light/Dark/narrow visual review;
- warning/error presentation;
- final merge/release review.


### SOCKS5 live validation

YouTube SOCKS5 is independent from Telegram proxy state and must be validated separately.

Unauthenticated proxy:

```bash
python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode inspect \
  --proxy-host 127.0.0.1 \
  --proxy-port 1080 \
  --report-file validation-reports/proxy-inspect.json
```

Authenticated proxy:

```bash
export YOUTUBE_SOCKS5_PASSWORD='your-proxy-password'

python scripts/youtube_manual_validate.py \
  --url "https://www.youtube.com/watch?v=<VIDEO_ID>" \
  --mode video_audio \
  --quality max_720p \
  --save-directory "/absolute/path/to/output" \
  --proxy-host 127.0.0.1 \
  --proxy-port 1080 \
  --proxy-user your-user \
  --acknowledge \
  --report-file validation-reports/proxy-download.json
```

Acceptance:
- Inspect and at least one Download succeed through a real SOCKS5 endpoint;
- changing proxy settings invalidates old Inspect metadata in the UI;
- report contains `request.proxy.enabled=true`;
- password value is absent from report/log/UI output;
- Telegram proxy state is not modified or reused automatically.
