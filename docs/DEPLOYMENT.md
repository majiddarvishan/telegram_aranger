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
  -p 8501:8501 \
  -v telegram_data:/data \
  telegram-harbor
```

The image defaults to:
- SQLite: `/data/telegram_manager.db`
- media cache: `/data/media`

These can still be overridden with environment variables.

## Docker Compose

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f telegram-harbor
```

The named `telegram_data` volume contains database state and downloaded media cache. Back up the database through `scripts/backup_db.py`; do not rely on copying a live WAL-mode database file.

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
