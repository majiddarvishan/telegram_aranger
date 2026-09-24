# Telegram Saved Messages Manager

A Streamlit multi-user Telegram archive manager using Pyrogram. No Keycloak is used.

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
telegram_saved_manager/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── config/
│   └── settings.py
├── db/
│   ├── database.py
│   ├── users.py
│   ├── telegram_accounts.py
│   └── tags.py
├── services/
│   ├── media_cache.py
│   ├── telegram_runtime.py
│   └── telegram_service.py
├── ui/
│   ├── auth.py
│   ├── sidebar.py
│   └── main.py
└── utils/
    ├── state.py
    └── date_range.py
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

The application deliberately does not use Keycloak.

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

The CookieManager instance is created once per Streamlit Web session and reused across reruns. This prevents `StreamlitDuplicateElementKey` errors caused by registering the same custom component key multiple times in one run.

`TgCrypto` is optional for Pyrogram. If it is unavailable on Python 3.14, Pyrogram falls back to its pure-Python implementation; functionality remains the same but cryptographic operations are slower.

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
