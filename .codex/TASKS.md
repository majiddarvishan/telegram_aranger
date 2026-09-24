# Tasks / Technical Findings

No source-code fixes were made during the 2026-09-24 review. Items below are findings for future work.

## P0 — Correctness
- [ ] Fix tag identity: `message_tags` currently uses only `(telegram_account_id, message_id)`. Telegram message IDs are chat-scoped, so include `chat_id` (and migrate existing data) to prevent cross-chat tag collisions.
- [ ] Rework historical message retrieval. `get_chat_history(..., limit=100)` limits iteration to the latest 100 messages; an older requested date range may never be reached in active chats.
- [ ] Decide pagination/load-more behavior instead of treating 100 messages as a complete date-range result.
- [ ] Verify timezone handling end-to-end between Pyrogram message datetimes and locally constructed date-range bounds.
- [ ] Ensure stopping a `TelegramRuntime` cleanly disconnects its active Pyrogram client before stopping the loop.

## P1 — Tests and regression safety
- [ ] Add unit tests for password hashing/authentication.
- [ ] Add tests for remember-me token creation, expiry, restore, and revocation.
- [ ] Add database tests for ownership isolation between Web users.
- [ ] Add tests for Telegram account save/update/delete behavior.
- [ ] Add tests for tag identity across multiple chats.
- [ ] Add service tests around date-range/history behavior using an injectable Telegram adapter/fake.
- [ ] Add UI-level smoke tests for login, account selection, filters, and deletion.
- [ ] Add a minimal CI workflow.

## P1 — Security hardening
- [ ] Decide production cookie policy explicitly; review `secure=None`, SameSite, HTTPS assumptions, and reverse-proxy deployment.
- [ ] Add login throttling/rate limiting or another brute-force mitigation.
- [ ] Move password policy/validation into a reusable service/domain layer, not UI only.
- [ ] Add cleanup for expired `web_sessions`.
- [ ] Define Fernet key rotation and backup procedure.
- [ ] Review whether sensitive proxy credentials should live in Streamlit session state only or be managed by a secret store.
- [ ] Document threat model for a multi-user deployment, especially host/database access.

## P2 — Performance / scalability
- [ ] Eliminate per-message N+1 SQLite tag lookups; load tags for a message set in one query.
- [ ] Add proper Telegram history pagination and lazy loading.
- [ ] Consider server-side/Telegram-side search strategy for large histories.
- [ ] Measure the impact of synchronous `.result()` waits on Streamlit responsiveness.
- [ ] Review SQLite contention under multiple concurrent Streamlit users.
- [ ] If multi-instance deployment is required, replace local Streamlit session/runtime assumptions and local SQLite with shared infrastructure.

## P2 — Data model / lifecycle
- [ ] Add schema versioning and migrations; current initialization only creates missing tables.
- [ ] Normalize tags if richer tag features are planned instead of comma-separated text.
- [ ] Define backup/restore for the SQLite database and Fernet key as one operational unit.
- [ ] Consider indexes after real query profiling.

## P3 — Operations
- [ ] Add structured logging and useful error context without leaking tokens, phone codes, passwords, session strings, or API secrets.
- [ ] Add Dockerfile and deployment documentation if container deployment is desired.
- [ ] Add health/readiness strategy appropriate for Streamlit + Telegram dependencies.
- [ ] Add dependency/security update policy; Pyrogram is pinned while other packages use ranges.
- [ ] Reconcile documentation claiming TgCrypto is optional with `requirements.txt` currently installing it unconditionally.

## P3 — UX / product definition
- [ ] Clarify whether the intended product is truly "Saved Messages Manager" or a general Telegram chat/message manager; current code lists all supported dialogs.
- [ ] Surface fetch-limit/pagination state so users do not assume the visible list is complete.
- [ ] Decide whether message deletion should require confirmation.
- [ ] Decide whether tag edits should support commas, normalization, rename, and deletion workflows.

## Review baseline
Branch before context commit:
- `others@5e7d1943b6289dc8c7def7f2a5426097016cc4c3`
- Compared with `main@76f7b4e56ec21873b6ede338f0800cc9c33df2f4`: ahead 5, behind 0.
