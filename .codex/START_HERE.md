# START HERE

## Repository
- Repository: `majiddarvishan/telegram_aranger`
- Current working branch: `feature/youtube-download`
- Current phase status: YouTube V1 implementation and automated readiness hardening are substantially complete. The latest confirmed full-green checkpoint during this handoff is `3b3ebf4b0cebbb8c842da8ba88c41c65c5c6350f`. Newer hardening exists after that checkpoint and branch HEAD must always be re-checked before edits. Remaining product acceptance is manual YT-P5 Light/Dark/narrow review, YT-P7 real YouTube/Windows/Docker/UI validation, and final merge/release review.
- Baseline: `main@ff7422284c7850ece9f3db9816cf600ff911a560`.
- Latest confirmed full-green YouTube checkpoint in this handoff: `3b3ebf4b0cebbb8c842da8ba88c41c65c5c6350f`.
- Handoff HEAD after additional hardening: `8b1e39a4d23e9d2a666843100a4cfd9309c35ee1` (re-check GitHub because the branch may advance again).
- The completed `gui` branch is already merged into `main`.

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
1. `.codex/NEXT_CHAT_PROMPT.md`
2. `.codex/YOUTUBE_PLAN.md`
3. `docs/YOUTUBE_DOWNLOAD_PLAN_FA.md`
4. `.codex/PROJECT_CONTEXT.md`
5. `.codex/ARCHITECTURE.md`
6. `.codex/DECISIONS.md`
7. `.codex/TASKS.md`
8. `.codex/SESSION.md`
9. `docs/MANUAL_TESTING.md`
10. `.codex/GUI_PLAN.md`

## Important rules
- Work on `feature/youtube-download` for this feature until the user explicitly requests merge/switch.
- The user explicitly approved implementation. YT-P1 through YT-P6 are implemented. Do not repeat them; continue with the remaining YT-P5 visual review and YT-P7 manual/live validation unless the user changes priority.
- Re-fetch branch HEAD before editing; do not assume these notes are newer than Git.
- Never commit Telegram API credentials, Fernet keys, session strings, phone codes, 2FA passwords, proxy passwords, browser remember tokens, SQLite data files, downloaded media, or backup artifacts.
- Preserve Web-user ownership checks for Telegram accounts and chat-scoped identity for tags/media.
- Database schema changes must increment/handle schema version and preserve existing data.
- Horizontal multi-instance deployment is not supported by the current local SQLite/runtime/cache architecture.
- Do not silently replace Pyrogram; its archived upstream status is documented and any replacement needs explicit session/behavior compatibility work.

## Local run

```bash
git checkout feature/youtube-download
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
