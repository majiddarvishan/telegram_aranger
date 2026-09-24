# Agent Working Notes

## Scope
This file is guidance for future coding/review sessions on `majiddarvishan/telegram_aranger`, currently on branch `feature/media-support`.

## Before changing code
- Read `.codex/START_HERE.md`, then `.codex/TASKS.md`.
- Re-fetch the current branch HEAD before editing; repository state may be newer than these notes.
- Prefer current code and green CI over historical review notes.
- Preserve modular boundaries across `config/`, `db/`, `services/`, `ui/`, `utils/`, `scripts/`, and `docs/`.
- Do not mark the final manual media-validation task complete without a real Telegram/browser run.

## Security invariants
Never expose or commit:
- `TELEGRAM_API_HASH`
- real Telegram API credentials
- Fernet encryption key
- exported/decrypted Telegram session strings
- phone login codes
- Telegram 2FA passwords
- remember-me bearer tokens
- proxy passwords
- production SQLite contents
- downloaded Telegram media
- backup artifacts

Preserve:
- Web-user ownership filtering on Telegram account reads/deletes.
- constant-time password hash comparison.
- encrypted-at-rest Telegram session storage.
- hashed server-side remember tokens.
- login throttling semantics.
- secret redaction in structured logs.

## Database changes
Current schema is versioned through `schema_meta`; current version is 2.

Any future schema change must:
- increment/handle schema version explicitly;
- preserve existing data or define a deliberate destructive migration;
- include migration regression tests;
- preserve foreign-key behavior;
- keep chat-scoped tag identity: `(telegram_account_id, chat_id, message_id)`.

SQLite is supported only for the current single-instance architecture. Do not imply horizontal multi-instance safety.

## Telegram changes
- Pyrogram calls must execute on the dedicated runtime event loop unless the runtime model is intentionally redesigned.
- Disconnect preserves the reusable saved session; Telegram logout invalidates the Telegram session and removes the local account.
- Runtime shutdown must disconnect the active client before stopping the loop.
- Message IDs are chat-scoped.
- History starts from the selected range end and uses explicit Load More result pagination.
- Media listing must stay metadata-only until an explicit user action.
- Interrupted media must never promote incomplete files into valid cache entries.
- Preserve force re-download behavior.
- Pyrogram upstream is archived; do not replace it silently.

## Streamlit changes
- The whole script reruns on interaction.
- Do not mutate widget-backed keys after widget creation in the same rerun.
- CookieManager must refresh browser cookies for Remember Me restore; do not regress to constructor snapshot-only behavior.
- Account changes must clear transient chat/message/media state.
- Permanent message deletion requires a second explicit confirmation.
- Large/slow Telegram actions should avoid opaque blocking UI; use progress where practical.

## Validation expectations
For meaningful code changes:
- require GitHub Actions to pass;
- include unit/regression coverage when feasible;
- verify auth/session restore if auth changes;
- verify ownership boundaries if DB access changes;
- verify migration from an older schema if schema changes;
- verify same numeric message ID in multiple chats if tag logic changes;
- verify media cache/recovery behavior if download logic changes;
- verify Docker build/health if deployment files change.

For real Telegram media acceptance, follow `docs/MANUAL_TESTING.md`.

## Operational references
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/DEPENDENCIES.md`
- `docs/SCALING.md`
- `docs/BACKUP_RESTORE.md`
- `docs/MANUAL_TESTING.md`

## Documentation hygiene
After meaningful changes, update:
- `.codex/SESSION.md`
- `.codex/TASKS.md`
- affected architecture/decision/context notes.
