# برنامه قابلیت دانلود YouTube برای Telegram Harbor

## وضعیت

- Branch: `feature/youtube-download`
- Baseline: `main@ff7422284c7850ece9f3db9816cf600ff911a560`
- این مرحله فقط تحلیل، تصمیم معماری و Task breakdown است.
- در این مرحله هیچ کد اجرایی YouTube نوشته نمی‌شود.

---

## هدف

اضافه کردن یک ابزار مستقل داخل Telegram Harbor برای دریافت محتوای عمومی YouTube، با این قابلیت‌ها:

- دریافت URL از کاربر؛
- نمایش اطلاعات محتوا قبل از دانلود؛
- انتخاب نوع خروجی؛
- گرفتن محل ذخیره از کاربر؛
- نمایش progress؛
- warning برای حقوق نشر / محدودیت‌های سرویس؛
- امکان ادامه دانلود بعد از تأیید warning، مشروط به اینکه دانلود نیازمند دور زدن DRM، paywall یا کنترل دسترسی نباشد.

---

## اصل مهم درباره Warning حقوق نشر و محدودیت سرویس

برنامه نباید ادعا کند که می‌تواند از روی metadata تشخیص حقوقی قطعی بدهد که یک ویدئو «دارای کپی‌رایت» است یا خیر.

طراحی پیشنهادی:

1. قبل از دانلود همیشه یک notice کوتاه نمایش داده شود:
   - کاربر مسئول داشتن حق/اجازه لازم برای ذخیره محتوا است؛
   - شرایط استفاده سرویس ممکن است روی دانلود محتوا محدودیت داشته باشد.

2. اگر metadata یا خطای سرویس نشانه‌ای از محدودیت نشان داد، Warning برجسته‌تر نمایش داده شود.

3. Warning به‌تنهایی download را قفل نمی‌کند.
   کاربر می‌تواند با تأیید صریح ادامه دهد.

4. اما برنامه نباید برای ادامه دانلود:
   - DRM را دور بزند؛
   - paywall را دور بزند؛
   - private/member-only/login-protected content را بدون دسترسی معتبر باز کند؛
   - مکانیزم کنترل دسترسی سرویس را bypass کند.

5. اگر محتوای عمومی به‌طور عادی توسط downloader قابل دسترس باشد، Warning مانع دانلود نیست.

این Warning یک تصمیم حقوقی نیست و فقط یک اطلاع‌رسانی محصولی است.

---

## کتابخانه پیشنهادی

برای implementation از یک abstraction روی `yt-dlp` استفاده شود.

مهم:
- UI مستقیماً به yt-dlp وابسته نشود.
- یک service layer مستقل ایجاد شود.
- تمام گزینه‌ها و progress hookها پشت interface داخلی پروژه قرار گیرند.
- اگر در آینده downloader تغییر کرد، UI نیاز به بازنویسی نداشته باشد.

---

# تجربه کاربری پیشنهادی

## Navigation

یک workspace مستقل داخل برنامه:

`Telegram Messages | YouTube Download`

یا معادل آن در Sidebar.

این feature نباید داخل Message Cardهای Telegram مخلوط شود.

---

## مرحله 1 — URL

ورودی:

`YouTube URL`

پشتیبانی اولیه:

- `youtube.com/watch?v=...`
- `youtu.be/...`
- URLهای عادی public video

در نسخه اول Playlist دانلود نشود مگر بعداً صریحاً اضافه شود.

---

## مرحله 2 — Inspect

قبل از Download، ابتدا metadata دریافت و نمایش داده شود:

- Title
- Channel / uploader
- Thumbnail
- Duration
- Video ID
- availability/restriction indicators در حد اطلاعاتی که downloader ارائه می‌دهد
- formatهای قابل استفاده
- estimated size در صورت موجود بودن

هیچ فایل media در مرحله Inspect دانلود نشود.

---

## مرحله 3 — Warning

دو لایه:

### General notice

همیشه نمایش داده شود:

`Only download content you are allowed to save. YouTube/service terms and copyright rules may apply.`

### Restriction warning

در صورت وجود signalهای مرتبط:

- age restriction
- live/premiere special state
- unavailable format
- geo/service restriction
- login/membership requirement
- other downloader restriction signal

نمایش شود.

برای محتوای عمومی که downloader بدون bypass قادر به دریافت است، کاربر با تأیید Warning می‌تواند ادامه دهد.

---

# محل ذخیره

## Requirement کاربر

محل ذخیره باید از خود کاربر گرفته شود.

## تصمیم پیشنهادی برای نسخه اول

یک فیلد اجباری:

`Save directory`

نمونه Windows:

`C:\Users\Majid\Downloads\TelegramHarbor`

نمونه Linux:

`/home/majid/Downloads/telegram-harbor`

### Validation

قبل از شروع Download:

- path خالی نباشد؛
- path normalize شود؛
- directory وجود داشته باشد یا با تأیید کاربر ساخته شود؛
- writable باشد؛
- filename نهایی از path خارج نشود؛
- filename sanitize شود؛
- collision policy مشخص باشد.

### نکته deployment

اگر برنامه روی سیستم دیگری/سرور اجرا شده باشد، این path متعلق به همان server host است.

UI باید واضح بنویسد:

`Files are saved on the machine running Telegram Harbor.`

برای browser-side folder picker می‌توان در فاز بعد custom Streamlit component بررسی کرد، اما scope نسخه اول نیست.

---

# حالت‌های خروجی

نسخه اول:

## Video + Audio

- خروجی معمولی قابل پخش؛
- کیفیت انتخابی؛
- در صورت نیاز merge با ffmpeg.

## Audio only

- استخراج audio؛
- container/codec مشخص؛
- ffmpeg requirement.

پیشنهاد کیفیت:

- Best available
- 1080p max
- 720p max
- 480p max

از exposing کردن تمام format IDهای فنی yt-dlp در UI اصلی خودداری شود.
Advanced format selection می‌تواند بعداً اضافه شود.

---

# وابستگی FFmpeg

برای merge کردن streamهای video/audio و برخی تبدیل‌های audio باید FFmpeg به‌عنوان dependency عملیاتی در نظر گرفته شود.

Taskهای لازم:

- Windows documentation؛
- Docker image؛
- deployment documentation؛
- startup capability check؛
- خطای قابل فهم در صورت نبود FFmpeg.

---

# Download workflow

State machine پیشنهادی:

1. `idle`
2. `inspecting`
3. `ready`
4. `warning_required`
5. `downloading`
6. `post_processing`
7. `completed`
8. `failed`
9. `cancelled` — در صورت اضافه شدن cancellation

---

# Progress

Progress hook downloader باید به UI translate شود.

نمایش:

- Download percentage
- downloaded bytes
- total/estimated bytes
- speed
- ETA
- current phase: Downloading / Merging / Extracting Audio
- final output filename

Raw yt-dlp log نباید مستقیم داخل UI dump شود.

---

# فایل خروجی

## Filename

نام فایل باید sanitize شود.

پیشنهاد template داخلی:

`<title> [<video_id>].<ext>`

مزایا:

- collision کمتر؛
- title خوانا؛
- traceability.

## Collision

نسخه اول:

اگر فایل وجود داشت:

- overwrite خودکار نکن؛
- suffix عددی اضافه کن یا از user confirmation استفاده کن.

ترجیح: suffix امن و خودکار.

---

# امنیت فایل‌سیستم

Telegram Harbor multi-user Web login دارد، بنابراین arbitrary path نوشتن روی یک server مشترک ریسک دارد.

پیشنهاد:

## Local/trusted-host mode

کاربر می‌تواند path دلخواه writable وارد کند.

## Hosted/multi-user mode

یک allowlist root اختیاری تعریف شود:

`YOUTUBE_DOWNLOAD_ROOTS`

کاربر فقط زیر rootهای مجاز path انتخاب کند.

در implementation قبل از write:

- `resolve()`
- containment check
- symlink/path traversal review
- writable check

انجام شود.

---

# Logging

در structured log:

مجاز:

- video ID
- selected mode
- quality
- duration
- output extension
- elapsed time
- success/failure

بهتر است log نشود:

- full URL با query اضافی
- cookies
- auth headers
- browser session data
- temporary access tokens

---

# Network / Authentication

نسخه اول:

- public YouTube content
- بدون browser-cookie import
- بدون username/password
- بدون automatic geo bypass
- بدون reuse خودکار SOCKS5 Telegram proxy

اگر بعداً proxy/cookies اضافه شد، باید به‌عنوان feature امنیتی جدا طراحی شود.

---

# Error handling

UI برای این خطاها پیام مشخص داشته باشد:

- invalid URL
- unsupported URL
- metadata unavailable
- video unavailable
- login required
- members-only/private content
- DRM/protected content
- FFmpeg unavailable
- save directory invalid/not writable
- not enough disk space در صورت قابل تشخیص بودن
- network failure
- post-processing failure
- output collision failure

---

# معماری پیشنهادی

## فایل‌های احتمالی

`services/youtube_service.py`

مسئول:

- validate URL
- inspect metadata
- normalize formats
- start download
- progress hooks
- post-processing
- error mapping

`ui/youtube.py`

مسئول:

- URL form
- metadata preview
- warning/acknowledgement
- path selection
- mode/quality selection
- progress
- completed result

`utils/download_paths.py`

مسئول:

- path normalization
- root containment
- filename sanitation
- collision handling

`config/settings.py`

تنظیمات احتمالی:

- `YOUTUBE_DOWNLOAD_ROOTS`
- `YOUTUBE_DEFAULT_QUALITY`
- `YOUTUBE_MAX_FILE_MB` در صورت نیاز
- `YOUTUBE_FFMPEG_PATH` در صورت نیاز

---

# تست

## Unit tests

بدون تماس واقعی با YouTube:

- URL validation
- metadata normalization
- warning classification
- path validation
- filename sanitization
- collision handling
- format selection
- progress-event normalization
- downloader error mapping
- no-bypass policy behavior

## UI smoke tests

- Inspect state
- warning acknowledgement
- path required
- quality selection
- Download disabled until required fields are valid
- progress state
- completion state
- failure state

## Integration test

به‌صورت manual یا optional:

- یک video عمومی و کوتاه که مجاز برای تست باشد
- download video+audio
- audio-only
- verify output path
- verify ffmpeg post-process
- verify Windows path handling

CI نباید به YouTube live network وابسته باشد.

---

# Task Phases

## YT-P0 — Requirement / architecture

- [x] Branch مستقل ایجاد شود.
- [x] scope نسخه اول مشخص شود.
- [x] save-directory requirement مشخص شود.
- [x] copyright/service warning semantics مشخص شود.
- [x] no-DRM/access-control-bypass boundary ثبت شود.
- [x] service/UI separation طراحی شود.
- [x] FFmpeg dependency در plan ثبت شود.
- [x] public-content-only baseline ثبت شود.

## YT-P1 — Dependency / service foundation

- [ ] اضافه کردن downloader dependency.
- [ ] اضافه کردن FFmpeg capability detection.
- [ ] ایجاد service abstraction.
- [ ] URL validation.
- [ ] metadata inspection.
- [ ] normalized error model.
- [ ] unit tests.

## YT-P2 — Save path / filesystem safety

- [ ] Save directory UI requirement.
- [ ] normalize/resolve path.
- [ ] writable validation.
- [ ] optional directory creation confirmation.
- [ ] filename sanitization.
- [ ] collision policy.
- [ ] optional allowed-root configuration for hosted mode.
- [ ] Windows/Linux tests.

## YT-P3 — Warning / acknowledgement

- [ ] General copyright/service notice.
- [ ] restriction-signal classification.
- [ ] explicit acknowledgement.
- [ ] warning remains non-blocking for ordinarily accessible public content.
- [ ] protected/access-controlled content is not bypassed.
- [ ] regression tests.

## YT-P4 — Download engine

- [ ] Video + audio mode.
- [ ] Audio-only mode.
- [ ] quality presets.
- [ ] progress hooks.
- [ ] post-processing status.
- [ ] final path reporting.
- [ ] failure cleanup.
- [ ] partial-file handling.

## YT-P5 — UI

- [ ] independent YouTube workspace.
- [ ] URL inspect form.
- [ ] metadata card.
- [ ] thumbnail.
- [ ] format controls.
- [ ] save-directory field.
- [ ] warning card.
- [ ] progress UI.
- [ ] completion state.
- [ ] responsive Light/Dark support.

## YT-P6 — Docker / Windows / docs

- [ ] Docker FFmpeg installation.
- [ ] Windows FFmpeg documentation.
- [ ] deployment documentation.
- [ ] README.
- [ ] manual testing checklist.
- [ ] CI tests without live YouTube dependency.

## YT-P7 — Validation

- [ ] Manual public test video.
- [ ] Windows save-path test.
- [ ] Docker test.
- [ ] Video+audio test.
- [ ] Audio-only test.
- [ ] warning flow test.
- [ ] error-path test.
- [ ] final review before merge.

---

# خارج از scope نسخه اول

- playlists
- full channels
- authenticated private content
- importing browser cookies
- membership bypass
- DRM bypass
- automatic geo-bypass
- batch URL queues
- scheduled downloads
- subtitles/chapters
- SponsorBlock
- thumbnail-only downloads

این موارد در صورت نیاز می‌توانند بعداً جداگانه طراحی شوند.
