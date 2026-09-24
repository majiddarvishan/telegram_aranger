# START HERE

## Repository
- Repository: `majiddarvishan/telegram_aranger`
- Working branch for this context: `feature/media-support`
- Reviewed on: 2026-09-24
- At review time, `others` was 5 commits ahead of `main` and 0 commits behind it.
- Head before adding these context files: `5e7d1943b6289dc8c7def7f2a5426097016cc4c3`.

## What this branch is
`others` contains a modular Streamlit application named **Telegram Saved Messages Manager**. It provides its own local multi-user Web authentication, lets each Web user attach one or more Telegram accounts through Pyrogram, stores encrypted Telegram session strings in SQLite, browses Telegram chats/messages, supports local per-message tags, search/date filtering, and can delete Telegram messages.

Despite the product name, the current UI can browse private chats, groups, supergroups, and channels, not only Telegram Saved Messages.

## Current feature objective
Add Telegram media support without eagerly downloading all media:
- display photo posts;
- play video posts inline;
- provide an explicit browser download button for videos;
- use lazy/on-demand downloads with bounded temporary caching.

No media implementation had been committed when this objective was added; see `.codex/TASKS.md`.

## Read order for future work
1. `.codex/PROJECT_CONTEXT.md`
2. `.codex/ARCHITECTURE.md`
3. `.codex/DECISIONS.md`
4. `.codex/TASKS.md`
5. `.codex/SESSION.md`

## Important rules
- Treat branch `feature/media-support` as the current feature branch. It was created from the merged `main` baseline.
- Do not assume `main` has the same architecture; `others` is a substantial refactor/reimplementation.
- Do not commit real Telegram API credentials, Fernet keys, session strings, phone codes, 2FA passwords, database files, or browser remember-me tokens.
- Before changing database schema, add a migration/versioning plan; the current code only uses `CREATE TABLE IF NOT EXISTS`.
- Preserve per-Web-user ownership checks when accessing Telegram accounts.
- Review the known correctness issues in `TASKS.md` before feature work.

## Local run
```bash
git checkout feature/media-support
python -m venv .venv
# activate the environment
pip install -r requirements.txt
cp .env.example .env
# fill TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_SESSION_ENCRYPTION_KEY
streamlit run app.py
```

Generate a Fernet key with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
