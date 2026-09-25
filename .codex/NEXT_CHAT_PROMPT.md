# NEXT CHAT PROMPT — Telegram Harbor / YouTube Download

Use the following prompt in a new ChatGPT conversation:

---

We are continuing work on the private GitHub repository:

`majiddarvishan/telegram_aranger`

Project name: **Telegram Harbor**

Work on branch:

`feature/youtube-download`

Do not work on `main` unless I explicitly ask.

Before doing anything:
1. Read `.codex/START_HERE.md`.
2. Read `.codex/YOUTUBE_PLAN.md`.
3. Read `docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`.
4. Read `.codex/PROJECT_CONTEXT.md`.
5. Read `.codex/DECISIONS.md`.
6. Read `.codex/TASKS.md`.
7. Read `.codex/SESSION.md`.
8. Re-check the current Git branch HEAD before making changes.

Important: implementation has been explicitly approved. YT-P1 through YT-P6 and extensive automated YT-P7 readiness hardening are already implemented. Latest confirmed full-green checkpoint in this handoff is `9bb8695f61e246cc96340f378413add67d298b50`; newer commits may exist, so re-check branch HEAD and CI first. Do not repeat completed hardening. Prioritize YT-P5 manual Light/Dark/narrow review and YT-P7 real YouTube/Windows/Docker/UI acceptance. Only change code when current CI/review/manual evidence exposes a concrete defect. Do not merge to main unless I explicitly ask.

Confirmed YouTube V1 requirements:

- Add YouTube download as an **independent workspace** inside Telegram Harbor, separate from Telegram message cards.
- V1 handles a **single public YouTube video URL** per job.
- First perform **Inspect** / metadata retrieval without downloading media.
- Show title, channel/uploader, thumbnail, duration, video ID, availability/restriction signals, formats/quality information, estimated size when available, and subtitle/caption tracks.
- Support:
  - Video + audio download.
  - Audio-only download.
  - Simple quality presets such as Best, max 1080p, max 720p, max 480p.
- User must explicitly provide the **Save directory**.
- On local installation the path is on the local machine running Telegram Harbor.
- On remote/server deployment the path belongs to the server host, not the browser client; the UI must say this clearly.
- Hosted/multi-user deployments should support configured allowed roots so users cannot write to arbitrary server locations.
- Validate and normalize the save path, verify it is writable, prevent path traversal/output escape, and handle Windows/Linux paths.
- The saved media basename must come from the **sanitized YouTube video title**, not the video ID.
- Optional subtitle download is included in V1.
- One subtitle track per job in V1.
- Distinguish **manual subtitle** from **auto-generated caption**.
- Preferred subtitle output is **SRT**.
- If SRT conversion is unavailable, report the actual fallback format such as VTT/original; do not silently use a misleading extension.
- When subtitle is enabled, media and subtitle files must use the same basename.
- Filename collisions must be handled as one output group, for example:
  - `My Video (2).mp4`
  - `My Video (2).srt`
- Do not overwrite existing files automatically by default.
- Show a concise **copyright / service-terms notice** before download.
- If metadata/downloader exposes restriction signals, show a stronger warning.
- These warnings are informational and acknowledgement-oriented, not a legal determination.
- For ordinarily accessible public content, warning alone must **not block download** after explicit acknowledgement.
- Do not implement DRM bypass, paywall bypass, private/member-only/login-protection bypass, or comparable technical access-control circumvention.
- No browser-cookie import or authenticated private-content support in V1.
- No automatic geo-bypass in V1.
- Do not automatically reuse the Telegram SOCKS5 proxy for YouTube.
- FFmpeg is an expected operational dependency for merge/audio extraction/post-processing.
- Support Windows and Docker FFmpeg setup/capability detection.
- Downloader implementation should be isolated behind a **service abstraction**; Streamlit UI must not depend directly on yt-dlp or another downloader library.
- Likely implementation areas:
  - `services/youtube_service.py`
  - `ui/youtube.py`
  - `utils/download_paths.py`
  - settings additions
  - tests
  Exact names may change if a cleaner architecture is found.
- Download progress should expose percentage, bytes, total/estimated bytes, speed, ETA, phase, post-processing status, and final output path where available.
- Raw downloader logs should not be dumped directly into the UI.
- CI must not depend on live YouTube network calls.
- Unit tests should use normalized/fake downloader data for URL validation, metadata normalization, warning states, path safety, filename sanitation, collision handling, subtitle selection, progress mapping, and error mapping.

Explicitly deferred from V1:
- playlists;
- full channels;
- browser-cookie import;
- authenticated/private/member-only content;
- DRM/access-control bypass;
- automatic geo-bypass;
- batch queues;
- scheduled downloads;
- multiple subtitle languages in one job;
- advanced subtitle management beyond the one selected track;
- chapters;
- SponsorBlock;
- thumbnail-only download.

Planning documents and tasks are already prepared. Continue from them rather than re-planning from scratch.

Continue from the remaining **YT-P5 visual review / YT-P7 manual validation**, keep CI green, and update `.codex/TASKS.md` and `.codex/SESSION.md` after each meaningful step.

---
