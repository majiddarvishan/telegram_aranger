# Agent Working Notes

## Scope
This file is guidance for future coding/review sessions on `majiddarvishan/telegram_aranger`, especially branch `others`.

## Before changing code
- Read all files under `.codex/`, starting with `START_HERE.md`.
- Inspect the current branch head and recent changes; these notes describe the repository as reviewed on 2026-09-24 and may become stale.
- Prefer evidence from current code over assumptions or old notes.
- Keep changes modular: configuration, DB, Telegram service/runtime, and UI are deliberately separated.

## Security invariants
Never expose or commit:
- `TELEGRAM_API_HASH`
- real `TELEGRAM_API_ID` if the user treats it as confidential
- Fernet encryption key
- exported/decrypted Telegram session strings
- phone login codes
- Telegram 2FA passwords
- remember-me bearer tokens
- real proxy passwords
- production SQLite database contents

Preserve:
- Web-user ownership filtering on Telegram account reads/deletes.
- Constant-time password hash comparison.
- encrypted-at-rest Telegram session storage.
- hashed server-side remember tokens.

## Database changes
The current project has no migration framework. Any schema change must include an explicit migration/backward-compatibility plan. In particular, fixing message-tag identity requires adding `chat_id` without silently discarding existing tags.

## Telegram changes
- Pyrogram calls must execute on the dedicated runtime event loop unless the runtime model is intentionally redesigned.
- Treat disconnect and logout differently: disconnect preserves the reusable saved session; logout invalidates the Telegram session and local account entry.
- Be careful with Telegram message ID scope: message IDs are not a global identifier across every chat.
- Avoid assumptions that 100 fetched messages cover an arbitrary requested date range.

## Streamlit changes
- Remember that the whole script reruns.
- Do not mutate widget-backed session-state keys after widget creation in the same rerun.
- CookieManager is intentionally kept as one instance in session state to avoid duplicate component registration.
- Avoid blocking operations in the main UI path where practical; current runtime wrappers still block while waiting for network completion.

## Validation expectations for future code work
At minimum:
- run syntax/import checks;
- run tests when a test suite exists;
- verify login/session restore behavior if auth is touched;
- verify Telegram account ownership boundaries if DB access changes;
- verify date-range browsing in chats with more than 100 recent messages if history logic changes;
- verify tags in two different chats that contain the same numeric message ID if tag logic changes.

## Documentation hygiene
Update `.codex/SESSION.md`, `.codex/TASKS.md`, and any affected architecture/decision notes after meaningful changes so a new session can continue without re-auditing the whole repository.
