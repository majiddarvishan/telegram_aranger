# START HERE

## Repository
- Repository: `majiddarvishan/telegram_aranger`
- Current working branch: `gui`
- Current phase status: stable application baseline is complete; `gui` is a visual-redesign planning/implementation branch.
- `gui` was created from `main@2bd6fbd18ac6ab03a38ee5ffc586c2d76c8ccc49`. Functional behavior should continue to follow `main`; visual redesign work is isolated here.

## What the project is
**Telegram Harbor** is a modular Streamlit Telegram message and media manager using Pyrogram.

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

The product name is **Telegram Harbor**. The GitHub repository name remains `telegram_aranger` for now.

## Current implementation status
Completed:
- P0 correctness fixes.
- P1 media feature.
- P1 regression/security hardening.
- P2 performance/data lifecycle work.
- P3 operations/UX work.
- Docker build + Streamlit health check in CI.
- Full automated regression suite in GitHub Actions.

Validation status:
- real Telegram/browser media validation has been completed successfully with no issues reported.
- automated GitHub Actions regression and Docker health checks are green.

`docs/MANUAL_TESTING.md` remains the repeatable acceptance checklist for future regressions.

## Read order for future work
1. `.codex/GUI_PLAN.md`
2. `.codex/PROJECT_CONTEXT.md`
3. `.codex/ARCHITECTURE.md`
4. `.codex/DECISIONS.md`
5. `.codex/TASKS.md`
6. `.codex/SESSION.md`
7. `docs/MANUAL_TESTING.md`
8. `docs/GUI_DESIGN_PLAN_FA.md`

## Important rules
- Work on `gui` for visual redesign unless the user explicitly switches branches. Do not merge GUI work into `main` without explicit approval.
- Re-fetch branch HEAD before editing; do not assume these notes are newer than Git.
- Never commit Telegram API credentials, Fernet keys, session strings, phone codes, 2FA passwords, proxy passwords, browser remember tokens, SQLite data files, downloaded media, or backup artifacts.
- Preserve Web-user ownership checks for Telegram accounts and chat-scoped identity for tags/media.
- Database schema changes must increment/handle schema version and preserve existing data.
- Horizontal multi-instance deployment is not supported by the current local SQLite/runtime/cache architecture.
- Do not silently replace Pyrogram; its archived upstream status is documented and any replacement needs explicit session/behavior compatibility work.

## Local run

```bash
git checkout gui
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
