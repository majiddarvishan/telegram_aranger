# Telegram Harbor

**Latest release:** `v1.1.0`

**Telegram Harbor** is a self-hosted, multi-user Telegram message and media manager built with Streamlit and Pyrogram.

It provides one central place to connect multiple Telegram accounts, browse private chats, groups, supergroups, channels and Saved Messages, search and tag messages, preview media, play videos, and download Telegram video files.

> Telegram Harbor is an independent project and is not affiliated with or endorsed by Telegram.

## Features

- Local multi-user web authentication with PBKDF2 password hashing.
- Multiple Telegram accounts per web user.
- Telegram phone login, verification code, and Telegram 2FA.
- Encrypted Telegram session strings using Fernet.
- Telegram logout and non-destructive disconnect.
- Chat selector for private chats, groups, supergroups, and channels.
- Saved Messages is selected by default when a Telegram account is opened.
- Responsive Light/Dark Telegram Harbor interface with content-first message cards.
- Date-range message filtering; defaults to the latest 7 calendar days.
- Compact Previous/Next day navigation in the message filter header.
- Search and per-message tags.
- Lazy photo preview for Telegram photo messages.
- Lazy inline playback for video/video-note/animation media.
- Browser video download with original/fallback file names and MIME types.
- Bounded temporary media cache with configurable TTL and size limits.
- SQLite persistence.
- Dedicated asyncio runtime thread for Pyrogram.
- Python 3.14 import compatibility workaround.
- SOCKS5 proxy support.
- Independent YouTube Download workspace for one public video URL per job.
- YouTube metadata Inspect before download, including formats and subtitle/caption tracks.
- Video + Audio and Audio-only output with simple quality presets.
- Optional one-track subtitle/caption download with Manual / Auto-generated labeling.
- Title-based non-overwriting output naming with matched media/subtitle basenames.
- Host save-directory validation, optional allowed roots, and FFmpeg capability checks.
- Optional independent SOCKS5 routing for YouTube Inspect and Download, with optional proxy authentication.

## Project layout

```text
telegram-harbor/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── config/
│   └── settings.py
├── db/
│   ├── auth_sessions.py
│   ├── database.py
│   ├── login_attempts.py
│   ├── dialogs.py
│   ├── tags.py
│   ├── telegram_accounts.py
│   └── users.py
├── services/
│   ├── media_cache.py
│   ├── telegram_runtime.py
│   ├── telegram_service.py
│   ├── youtube_service.py
│   ├── youtube_policy.py
│   └── youtube_download.py
├── ui/
│   ├── auth.py
│   ├── main.py
│   ├── sidebar.py
│   ├── theme.py
│   └── youtube.py
├── utils/
│   ├── date_range.py
│   ├── logging.py
│   ├── download_paths.py
│   └── state.py
├── scripts/
│   ├── backup_db.py
│   └── restore_db.py
├── docs/
│   ├── BACKUP_RESTORE.md
│   ├── DEPENDENCIES.md
│   ├── DEPLOYMENT.md
│   ├── MANUAL_TESTING.md
│   ├── SCALING.md
│   └── SECURITY.md
└── tests/
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and a valid Fernet key.

Generate the Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

4. Start:

```bash
streamlit run app.py
```

### Windows / Python 3.14

If an older environment shows:

```text
TgCrypto is missing! Pyrogram will work the same, but at a much slower speed.
```

reinstall the crypto acceleration dependency in the active virtual environment:

```powershell
python -m pip uninstall -y TgCrypto tgcrypto2
python -m pip install -r requirements.txt
python -c "import tgcrypto; print(tgcrypto.__file__)"
```

The last command should print the installed `tgcrypto` module path without an import error.

For YouTube output support, install FFmpeg/FFprobe on Windows and make sure both executables are available on `PATH`:

```powershell
ffmpeg -version
ffprobe -version
```

Restart the terminal/Streamlit process after changing `PATH`.

## Important

Telegram sessions are encrypted at rest with the Fernet key. Keep `TELEGRAM_SESSION_ENCRYPTION_KEY` secret and back it up securely. Losing it makes stored Telegram sessions undecryptable.

Telegram Harbor deliberately uses its own local authentication instead of Keycloak.

## Web Login Remember Me

The Web login supports a persistent **Remember me** session.

Configure the lifetime in `.env`:

```env
WEB_REMEMBER_ME_DAYS=7
WEB_COOKIE_SECURE=false
WEB_COOKIE_SAMESITE=lax
WEB_LOGIN_MAX_ATTEMPTS=5
WEB_LOGIN_WINDOW_MINUTES=15
```

The browser receives a random persistent token. Only its SHA-256 hash is stored in SQLite. The token is revoked when the user logs out of the Web application. Failed Web logins are throttled by normalized username using the configured attempt/window limits.

For HTTPS production deployments, set `WEB_COOKIE_SECURE=true`. See `docs/SECURITY.md` for reverse-proxy and SameSite guidance.

The project uses `extra-streamlit-components` for the browser cookie required to keep the login across Streamlit sessions.


### Remember Me / CookieManager

Telegram Harbor keeps one CookieManager instance per Streamlit Web session and reuses it across reruns. This prevents `StreamlitDuplicateElementKey` errors caused by registering the same custom component key multiple times in one run.

`tgcrypto2` is installed by this project's `requirements.txt`. It keeps the import name `tgcrypto`, so it is drop-in compatible with Pyrogram while providing modern Python/Windows wheels. See `docs/DEPENDENCIES.md`.

## Media cache and limits

Media is downloaded only when the user requests a preview/playback or prepares a video download. The application does not eagerly download every media item while listing messages.

Optional settings:

```env
MEDIA_CACHE_DIR=.cache/telegram_media
MEDIA_CACHE_TTL_HOURS=24
MEDIA_CACHE_MAX_MB=2048
MEDIA_PREVIEW_MAX_MB=200
MEDIA_DOWNLOAD_MAX_MB=200
TELEGRAM_DIALOG_LIMIT=100
```

The cache path is ignored by Git. Cache entries are namespaced by Telegram account, chat, and message, and old files are removed by TTL/size cleanup. Increase the preview/download limits only when the Streamlit host has enough memory/disk capacity.


## YouTube Download workspace

The YouTube workspace is separate from Telegram message cards.

V1:
- accepts one public YouTube video URL per job;
- can optionally route YouTube Inspect and Download through an independent SOCKS5 proxy;
- performs an Inspect step before downloading media;
- supports Video + Audio and Audio-only output;
- offers Best, max 1080p, max 720p and max 480p quality presets;
- supports one optional Manual or Auto-generated subtitle/caption track;
- prefers SRT and reports the actual fallback format if SRT conversion is unavailable;
- requires an explicit host filesystem Save directory;
- never overwrites an existing output automatically;
- uses the sanitized video title as the shared media/subtitle basename.

The Save directory belongs to the machine running Telegram Harbor. On a remote deployment it is a server path, not a path on the browser user's computer.

For hosted/multi-user deployments, configure optional allowed roots:

```env
YOUTUBE_DOWNLOAD_ROOTS=/srv/telegram-harbor/youtube
```

Use the platform path separator for multiple roots. The Docker image defaults to `/data/youtube`.

Telegram Harbor shows a rights/service notice and stronger restriction warnings where metadata exposes them. The warning is informational and does not make a legal determination. V1 supports optional signed-in session cookies for otherwise supported videos, but does not implement DRM bypass, paywall bypass, private/member-only/premium-content access, authenticated private-content support, or automatic geo-bypass.

FFmpeg and FFprobe are required for full output support.

The YouTube SOCKS5 proxy is configured inside the YouTube workspace and is disabled by default. It does not automatically reuse the Telegram SOCKS5 settings. Proxy credentials remain session-only in the UI and are not persisted by Telegram Harbor.

## Security

For production cookie settings, Web-login throttling, Fernet key backup/rotation, proxy-secret handling, media-cache security, and the multi-user threat model, see `docs/SECURITY.md`.


## Docker

Build and run with Docker Compose:

```bash
docker compose up -d --build
```

The container exposes port 8501, runs as a non-root user, persists the database/media cache under `/data`, includes FFmpeg/FFprobe, provides `/data/youtube` as the default allowed YouTube save root, and uses Streamlit's `/_stcore/health` endpoint for its container health check.

See `docs/DEPLOYMENT.md` for Telegram Harbor production deployment guidance.


## Validation

Automated unit/regression tests and Docker build/health checks run in GitHub Actions.

For real Telegram/browser acceptance—photo preview, video playback, browser download, and interrupted-transfer recovery—follow `docs/MANUAL_TESTING.md`.


## Dialog cache

Telegram Harbor caches the latest Telegram chat/dialog list in SQLite per Telegram account. Normal application startup reads that cache instead of calling Telegram `messages.GetDialogs` repeatedly.

- The first uncached load fetches at most `TELEGRAM_DIALOG_LIMIT` dialogs (default: 100).
- Dialog cache rows persist Pyrogram peer type/access-hash metadata so channel/supergroup peers can be restored after process restart.
- Existing pre-v4 dialog caches are refreshed once to populate peer metadata.
- **Refresh Chats** explicitly refreshes the cache from Telegram.
- If an explicit refresh fails and cached dialogs exist, the cached list remains usable.
- Concurrent Streamlit sessions share a process-level refresh lock so only one uncached dialog refresh is sent at a time.


### YouTube authenticated session

Telegram Harbor can optionally reuse a signed-in browser session for YouTube Inspect/Download when the browser profile exists on the same machine and under the same OS user as Telegram Harbor.

- No Google username/password is requested.
- OAuth is not used.
- **Browser session** is the preferred local-install mode and uses yt-dlp's browser-cookie integration.
- Supported browser choices include Auto, Chrome, Firefox, Edge, Brave, Chromium, Vivaldi, Opera, Safari and Whale.
- An optional browser profile name/path can be supplied.
- Browser cookie values are not persisted to SQLite, logs, or validation reports.
- For Docker/remote deployments, where the user's browser is on another machine, a youtube.com-only Netscape `cookies.txt` upload remains available as a fallback.
- Authenticated mode can be combined with the independent YouTube SOCKS5 proxy.
- Private/member-only/premium/DRM content remains blocked by product policy.

