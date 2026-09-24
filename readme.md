# Telegram Harbor

**Latest release:** `v1.0.1`

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
- Date-range message filtering; defaults to the latest 7 calendar days.
- Previous/Next Day navigation at the bottom of the page.
- Search and per-message tags.
- Lazy photo preview for Telegram photo messages.
- Lazy inline playback for video/video-note/animation media.
- Browser video download with original/fallback file names and MIME types.
- Bounded temporary media cache with configurable TTL and size limits.
- SQLite persistence.
- Dedicated asyncio runtime thread for Pyrogram.
- Python 3.14 import compatibility workaround.
- SOCKS5 proxy support.

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
│   ├── tags.py
│   ├── telegram_accounts.py
│   └── users.py
├── services/
│   ├── media_cache.py
│   ├── telegram_runtime.py
│   └── telegram_service.py
├── ui/
│   ├── auth.py
│   ├── main.py
│   └── sidebar.py
├── utils/
│   ├── date_range.py
│   ├── logging.py
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

`TgCrypto` is installed by this project's `requirements.txt` and is part of the supported deployment profile. Upstream Pyrogram can technically run without it, but this repository does not treat that as the normal installation path. See `docs/DEPENDENCIES.md`.

## Media cache and limits

Media is downloaded only when the user requests a preview/playback or prepares a video download. The application does not eagerly download every media item while listing messages.

Optional settings:

```env
MEDIA_CACHE_DIR=.cache/telegram_media
MEDIA_CACHE_TTL_HOURS=24
MEDIA_CACHE_MAX_MB=2048
MEDIA_PREVIEW_MAX_MB=200
MEDIA_DOWNLOAD_MAX_MB=200
```

The cache path is ignored by Git. Cache entries are namespaced by Telegram account, chat, and message, and old files are removed by TTL/size cleanup. Increase the preview/download limits only when the Streamlit host has enough memory/disk capacity.


## Security

For production cookie settings, Web-login throttling, Fernet key backup/rotation, proxy-secret handling, media-cache security, and the multi-user threat model, see `docs/SECURITY.md`.


## Docker

Build and run with Docker Compose:

```bash
docker compose up -d --build
```

The container exposes port 8501, runs as a non-root user, persists the database/media cache under `/data`, and uses Streamlit's `/_stcore/health` endpoint for its container health check.

See `docs/DEPLOYMENT.md` for Telegram Harbor production deployment guidance.


## Validation

Automated unit/regression tests and Docker build/health checks run in GitHub Actions.

For real Telegram/browser acceptance—photo preview, video playback, browser download, and interrupted-transfer recovery—follow `docs/MANUAL_TESTING.md`.
