# Telegram Harbor Deployment

## Docker

The container runs Streamlit as a non-root user on port 8501.

Build:

```bash
docker build -t telegram-harbor .
```

Run with an environment file and persistent data volume:

```bash
docker run --rm \
  --env-file .env \
  -e YOUTUBE_DOWNLOAD_ROOTS=/data/youtube \
  -p 8501:8501 \
  -v telegram_data:/data \
  telegram-harbor
```

The image defaults to:
- SQLite: `/data/telegram_manager.db`
- media cache: `/data/media`
- YouTube allowed save root: `/data/youtube`

The image also installs `ffmpeg` and `ffprobe`, which are required for YouTube video/audio merge, audio extraction and subtitle conversion.

`docker compose` defaults `YOUTUBE_DOWNLOAD_ROOTS` to `/data/youtube` even when the copied `.env` leaves that setting empty. For direct `docker run --env-file .env`, pass the explicit `-e YOUTUBE_DOWNLOAD_ROOTS=/data/youtube` shown above so an empty env-file value cannot remove the container restriction.

These can still be overridden with environment variables.

## Docker Compose

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f telegram-harbor
```

The named `telegram_data` volume contains database state, Telegram media cache and YouTube output saved below `/data/youtube`. Back up the database through `scripts/backup_db.py`; do not rely on copying a live WAL-mode database file.

## Health check

The image uses Streamlit's health endpoint:

```text
GET /_stcore/health
```

Docker marks the container unhealthy when that endpoint cannot be reached.

This is a process/readiness check for Streamlit. It does **not** guarantee that Telegram is reachable or that a user's saved Telegram session is valid. Telegram connectivity is user/session-specific and should not make the whole Web application unhealthy.

## Production reverse proxy

For production:
1. terminate HTTPS at the reverse proxy/load balancer;
2. set `WEB_COOKIE_SECURE=true`;
3. expose Streamlit only through the proxy;
4. restrict direct access to port 8501;
5. configure request/source-IP throttling at the proxy;
6. persist `/data` on protected storage;
7. keep `.env` and Fernet keys outside the image;
8. use the backup/restore procedure before upgrades.

See:
- `docs/SECURITY.md`
- `docs/BACKUP_RESTORE.md`
- `docs/SCALING.md`

## Multi-instance warning

Do not scale the current image to multiple replicas against the same local SQLite file or local media volume. The current architecture is single-host/single-instance by design. See `docs/SCALING.md` for the redesign required before horizontal scaling.


## YouTube save paths

The YouTube Save directory is always interpreted on the machine running Telegram Harbor.

- Native/local installation: it is a local filesystem path on that machine.
- Remote/server installation: it is a server-host path, not a browser-client path.
- Docker: the default allowed root is `/data/youtube`.

For Docker, enter `/data/youtube` or a subdirectory such as `/data/youtube/user-a` in the UI. The existing `telegram_data:/data` volume keeps these files persistent.

To store YouTube output on a specific host directory instead of the named volume, mount it and set the allowed root explicitly, for example:

```bash
docker run --rm \
  --env-file .env \
  -e YOUTUBE_DOWNLOAD_ROOTS=/downloads \
  -p 8501:8501 \
  -v /srv/telegram-harbor/youtube:/downloads \
  -v telegram_data:/data \
  telegram-harbor
```

For a shared/multi-user server, keep `YOUTUBE_DOWNLOAD_ROOTS` configured so users cannot write to arbitrary server locations. Multiple roots use the operating system path separator.

The application validates and resolves the directory, verifies writability and prevents output from escaping the selected/allowed root. A missing directory is created only when the user explicitly selects the create-directory option.

## Native Windows FFmpeg

Install an FFmpeg build that includes both `ffmpeg.exe` and `ffprobe.exe`, add its `bin` directory to `PATH`, then verify from the same shell that will run Streamlit:

```powershell
ffmpeg -version
ffprobe -version
```

Restart the shell and Telegram Harbor after changing `PATH`. The YouTube workspace reports FFmpeg/FFprobe capability before download.

## YouTube access boundary

YouTube V1 supports ordinarily accessible public content only. It does not import browser cookies, authenticate to private/member-only content, bypass DRM/paywalls/access controls or automatically perform geo-bypass. The Telegram SOCKS5 proxy is not reused automatically for YouTube.


## Build identity

Docker images support the optional build argument `TELEGRAM_HARBOR_BUILD_SHA`. It is used by the YouTube manual-validation report to identify the exact source revision inside an image where `.git` is intentionally excluded.

Recommended direct build:

```bash
docker build \
  --build-arg TELEGRAM_HARBOR_BUILD_SHA="$(git rev-parse HEAD)" \
  -t telegram-harbor:local .
```

Recommended Compose build:

```bash
export TELEGRAM_HARBOR_BUILD_SHA="$(git rev-parse HEAD)"
docker compose build
```

This value is source identity only; do not put secrets in the build argument.
