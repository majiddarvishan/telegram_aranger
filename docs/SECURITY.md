# Telegram Harbor Security Notes

## Scope

This application is designed primarily for trusted self-hosted or small-team use. It stores local Web users, encrypted Telegram session strings, remembered Web-login sessions, message tags, and login-attempt metadata in SQLite.

Host administrators with filesystem access remain inside the trust boundary: they can read the SQLite database, environment variables, process memory, and the configured Fernet key.

## Web authentication

Passwords are hashed with PBKDF2-HMAC-SHA256 using a random 32-byte salt and 310,000 iterations.

The password policy is enforced in the database/domain layer, not only in Streamlit UI. Passwords shorter than 8 characters are rejected by `db.users.create_user()`.

Failed Web-login attempts are recorded in SQLite by normalized username. Defaults:

```env
WEB_LOGIN_MAX_ATTEMPTS=5
WEB_LOGIN_WINDOW_MINUTES=15
```

A successful login clears prior failed attempts for that username. Old attempts are deleted as the rate-limit window advances.

This is basic account-level brute-force protection. For Internet-facing deployments, also apply reverse-proxy/WAF rate limiting by source IP.

## Remember-me cookies

Remember-me tokens are random bearer tokens. Only SHA-256 hashes are stored in SQLite.

Cookie defaults favor local HTTP development:

```env
WEB_COOKIE_SECURE=false
WEB_COOKIE_SAMESITE=lax
WEB_REMEMBER_ME_DAYS=7
```

For production behind HTTPS:

```env
WEB_COOKIE_SECURE=true
WEB_COOKIE_SAMESITE=lax
```

Use `WEB_COOKIE_SAMESITE=none` only when cross-site cookie behavior is actually required; the application rejects that setting unless `WEB_COOKIE_SECURE=true`.

The cookie path is `/`, expiration is UTC-based, and `max_age` is set to the same configured lifetime.

Expired or malformed remembered-login sessions are removed at application startup.

## HTTPS and reverse proxy

For a network-accessible deployment:

1. Terminate TLS at a trusted reverse proxy or load balancer.
2. Set `WEB_COOKIE_SECURE=true`.
3. Restrict direct access to the Streamlit backend port.
4. Apply source-IP rate limiting at the proxy in addition to application username throttling.
5. Do not expose SQLite, `.env`, media cache, or logs as static files.
6. Back up application data only to encrypted storage.

## Fernet key management

`TELEGRAM_SESSION_ENCRYPTION_KEY` encrypts exported Telegram session strings stored in SQLite.

Treat the SQLite database and Fernet key as a single recovery unit:
- Back up both.
- Store the key separately from the database backup when possible.
- Protect backups with access controls and encryption.
- Do not commit the key to Git.
- Do not print it in logs.

### Rotation procedure

A key must not simply be replaced in `.env`; existing Telegram sessions would become unreadable.

Safe rotation procedure:

1. Stop application writes.
2. Create a verified backup of the SQLite database.
3. Preserve the old Fernet key until rotation is verified.
4. Generate a new Fernet key.
5. For every `telegram_accounts.encrypted_session` row:
   - decrypt with the old key;
   - encrypt the same session string with the new key;
   - update the row inside a database transaction.
6. Update `TELEGRAM_SESSION_ENCRYPTION_KEY` to the new key.
7. Start the application and verify every stored Telegram account can restore.
8. Keep the old key in protected rollback storage until the new backup is verified.
9. Retire the old key according to the operator's secret-retention policy.

If any row cannot be decrypted during rotation, abort and roll back rather than partially rotating the database.

## Proxy credentials

SOCKS5 username/password currently live only in Streamlit session state and are not persisted in SQLite.

Implications:
- They disappear when the Web session is cleared.
- They can still exist in process memory.
- They must never be included in application logs or diagnostics.
- For centralized production deployment, prefer injecting fixed proxy credentials from a secret manager instead of asking users to enter shared infrastructure credentials.

## Telegram sessions

Exported Telegram session strings effectively authorize Telegram access and must be treated as secrets.

They are encrypted at rest with Fernet, but anyone who obtains both the database and Fernet key can decrypt them. Telegram login codes and 2FA passwords must remain transient and must never be persisted or logged.

## Media cache

Telegram media cache is local and intentionally excluded from Git.

The cache is namespaced by Telegram account, chat, and message. Incomplete `.part` downloads are removed, cached files are validated against Telegram-reported size when available, and cache TTL/size limits are configurable.

A host administrator can still read cached media files. Put the cache on appropriately protected storage.

## Multi-user threat model

The application enforces ownership at the SQLite query layer for Telegram account lookup/deletion.

Important boundaries:
- Web users must not be able to fetch another user's Telegram account row by ID.
- Deleting an account must not delete another user's tags or account metadata.
- Message tags are scoped by Telegram account + chat + message.
- Application administrators/host operators are trusted and are not isolated from user secrets by this architecture.

If strong tenant isolation is required, move from a single local Streamlit/SQLite process to a service architecture with centralized authentication, a shared database, per-request authorization, audited secret access, and isolated worker/runtime credentials.


## YouTube SOCKS5 proxy credentials

YouTube has an optional SOCKS5 proxy configuration independent from Telegram proxy state.

Security rules:
- disabled by default;
- proxy password is kept only in the active Streamlit session when entered through the UI;
- Telegram Harbor does not persist the YouTube proxy password to SQLite;
- validation reports store only safe metadata and never the password value;
- the manual validation CLI reads an optional password from `YOUTUBE_SOCKS5_PASSWORD` (or the environment variable selected with `--proxy-password-env`) rather than accepting a plaintext password argument;
- raw yt-dlp `proxy` injection through generic downloader options remains blocked;
- enabling SOCKS5 does not enable cookies, authenticated YouTube sessions, geo-bypass flags, or access-control bypass.

Treat any proxy username/password as a secret and prefer a dedicated secret manager/environment injection for shared hosted deployments.


## YouTube authenticated sessions

Telegram Harbor supports optional signed-in YouTube access without collecting Google credentials.

Preferred local mode — Browser session:
- uses yt-dlp's supported browser-cookie integration;
- reads cookies from a browser profile on the **same host and OS user** that runs Telegram Harbor;
- supports an optional profile name/path;
- does not copy browser cookie values into SQLite, structured logs, or validation reports;
- validation reports record only the auth source, selected browser, and whether a profile was configured;
- Auto detection checks standard browser-profile locations only; it does not read cookie contents until an authenticated Inspect/Download is explicitly started.

Fallback mode — `cookies.txt`:
- intended for Docker/remote installs where the browser is not on the backend host;
- accepts only Mozilla/Netscape format with `youtube.com` cookie rows;
- upload remains session-only;
- cookie bytes are materialized to a restrictive temporary file only while yt-dlp runs and are deleted afterward;
- cookie file path, names, and values are never written to validation reports.

General rules:
- no Google username/password fields;
- no OAuth flow;
- raw yt-dlp `cookiefile` / `cookiesfrombrowser` injection remains blocked through generic options;
- authenticated mode does not override product blocks for private, members-only, premium, or DRM-protected content;
- browser/account cookies are sensitive session credentials; enable this only when needed and prefer a dedicated YouTube account/session where practical.

Operational limitation:
- a Docker container or remote server cannot directly reuse cookies from a browser running on the user's laptop/desktop. In that topology use the `cookies.txt` fallback or run Telegram Harbor locally under the browser's OS user.

