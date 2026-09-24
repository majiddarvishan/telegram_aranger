# Telegram Harbor Scaling and Performance

## Current deployment model

The application is intentionally a single-host Streamlit application.

Each browser session owns:
- Streamlit session state;
- one `TelegramRuntime` thread/event loop;
- at most one active Pyrogram client.

Shared local resources are:
- one SQLite database;
- one local media-cache directory.

This model is appropriate for a trusted self-hosted deployment or a small number of concurrent users. It is not a horizontally scalable multi-instance architecture.

## Telegram history

History retrieval starts from the selected date range's end using Pyrogram `offset_date`, then walks backward until the range start. The configured message limit applies to results inside the selected range.

The UI exposes the current loaded count and provides **Load More Messages** in fixed increments. This avoids treating an arbitrary 100-message window as complete.

## Search strategy

Current text search is deliberately local over the messages already loaded for the selected date range.

Why:
- Streamlit text inputs rerun frequently while a user types.
- Triggering Telegram full-history search on every rerun would add network latency and API load.
- Pyrogram's high-level `search_messages()` API does not provide the same explicit start/end date parameters as the application's date-range UI.

If full-history search becomes a product requirement, implement it as an explicit submit action rather than per-keystroke behavior. The recommended design is:
1. user enters search text and submits;
2. call Telegram server-side search;
3. apply the selected date bounds to returned messages;
4. paginate results independently from normal history browsing;
5. cache the query signature/results for reruns.

## Synchronous Telegram waits

Most existing service wrappers call `TelegramRuntime.run()`, which waits synchronously for a coroutine submitted to the dedicated Telegram event loop. The network work is off the Streamlit thread, but the Streamlit rerun waits for the result.

`TelegramRuntime` now records:
- `run_calls`;
- `last_wait_seconds`;
- `max_wait_seconds`.

Media downloads are handled separately through `submit()` so the UI can show byte-level progress while waiting.

If normal Telegram calls become slow under real workload, use these metrics to identify which UI operations need the same asynchronous/progress treatment.

## SQLite concurrency

Every connection enables:
- WAL journal mode;
- foreign keys;
- 30-second SQLite busy timeout;
- `synchronous=NORMAL`.

The application also batch-loads message tags to avoid one SQLite query per rendered message.

SQLite remains a single-host database. WAL improves read/write concurrency but does not make a local SQLite file safe shared storage for multiple application instances.

## Multi-instance deployment

Horizontal scaling is **not supported by the current architecture**.

A future multi-instance design should replace:
- local SQLite with a shared transactional database, e.g. PostgreSQL;
- local media cache with shared/object storage or instance-independent cache semantics;
- Streamlit-only session/runtime ownership with server-side session state;
- one in-process Pyrogram runtime per browser with explicit Telegram connection ownership/worker routing.

The application must also ensure that the same Telegram account is not concurrently controlled by conflicting workers unless that behavior is deliberately designed and tested.

## Indexing policy

Current hot lookups are already covered by primary/unique/index keys:
- users by unique username;
- Telegram accounts by `(user_id, telegram_user_id)`;
- remembered sessions by token hash and user ID;
- login attempts by `(username, attempted_at)`;
- message tags by `(telegram_account_id, chat_id, message_id)`.

Additional indexes should be added only after a measured query requires them rather than pre-emptively increasing write cost.
