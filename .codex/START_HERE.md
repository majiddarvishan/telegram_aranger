# START HERE

## Repository
- Repository: `majiddarvishan/telegram_aranger`
- Current working branch: `feature/media-support`
- Current phase status: P0/P1/P2/P3 automated implementation is complete; real Telegram/browser media validation remains open.
- Branch was created from the merged `main` baseline and is currently the source of truth for this feature set.

## What the project is
This is a modular Streamlit Telegram message manager using Pyrogram.

It provides:
- local multi-user Web authentication;
- persistent Remember Me sessions;
- multiple Telegram accounts per Web user;
- encrypted Telegram session storage;
- private/group/supergroup/channel browsing;
- date-range history with Load More pagination;
- text search over loaded messages;
- chat-scoped local tags;
- Telegram message deletion with confirmation;
- lazy photo preview;
- inline video/video-note/animation playback;
- browser video download;
- interrupted-media recovery and explicit re-download;
- SQLite persistence and schema migrations;
- structured JSON logging;
- Docker/Compose deployment;
- automated GitHub Actions regression tests.

The UI still uses the legacy title **Telegram Saved Messages Manager**, but the product behavior is a general Telegram message manager.

## Current implementation status
Completed:
- P0 correctness fixes.
- P1 media feature.
- P1 regression/security hardening.
- P2 performance/data lifecycle work.
- P3 operations/UX work.
- Docker build + Streamlit health check in CI.
- Full automated regression suite in GitHub Actions.

Still open:
- real Telegram/browser validation for small and large photos/videos and browser video download.

Use `docs/MANUAL_TESTING.md` for that checklist. Do not mark the final media-validation task complete without actually running those real Telegram/browser scenarios.

## Read order for future work
1. `.codex/PROJECT_CONTEXT.md`
2. `.codex/ARCHITECTURE.md`
3. `.codex/DECISIONS.md`
4. `.codex/TASKS.md`
5. `.codex/SESSION.md`
6. `docs/MANUAL_TESTING.md`

## Important rules
- Treat `feature/media-support` as the current source branch unless the user explicitly switches branches.
- Re-fetch branch HEAD before editing; do not assume these notes are newer than Git.
- Never commit Telegram API credentials, Fernet keys, session strings, phone codes, 2FA passwords, proxy passwords, browser remember tokens, SQLite data files, downloaded media, or backup artifacts.
- Preserve Web-user ownership checks for Telegram accounts and chat-scoped identity for tags/media.
- Database schema changes must increment/handle schema version and preserve existing data.
- Horizontal multi-instance deployment is not supported by the current local SQLite/runtime/cache architecture.
- Do not silently replace Pyrogram; its archived upstream status is documented and any replacement needs explicit session/behavior compatibility work.

## Local run

```bash
git checkout feature/media-support
python -m venv .venv
# activate the virtual environment
pip install -r requirements.txt
cp .env.example .env
# fill TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_SESSION_ENCRYPTION_KEY
streamlit run app.py
```

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Docker run

```bash
docker compose up -d --build
docker compose ps
```

See `docs/DEPLOYMENT.md`, `docs/SECURITY.md`, `docs/SCALING.md`, and `docs/BACKUP_RESTORE.md`.
