# Decisions / Observed Design Choices

These are **observed implementation decisions** in branch `others`, not necessarily permanent product requirements. Update this file when the user explicitly changes one.

## D-001 — Streamlit is the application shell
Status: current

The product is a Streamlit application. UI, session state, authentication screens, account management, and message browsing all run through Streamlit reruns.

## D-002 — Local authentication, no Keycloak
Status: current

The branch intentionally uses its own SQLite-backed Web users rather than Keycloak or another external IdP.

## D-003 — SQLite is the only application database
Status: current

Users, remembered Web sessions, Telegram account metadata/session ciphertext, and local message tags are persisted in one SQLite file.

## D-004 — Telegram sessions are exported and encrypted at rest
Status: current

Pyrogram clients are in-memory. Their exported session string is encrypted with Fernet and saved in SQLite. The application requires the same encryption key to restore accounts later.

Operational implication: loss/rotation of the Fernet key without a migration strategy makes existing Telegram sessions unreadable.

## D-005 — One Telegram client/runtime per Streamlit browser session
Status: current

A dedicated daemon thread and asyncio event loop are stored in Streamlit session state. The runtime holds at most one active Pyrogram client.

## D-006 — Telegram proxy is UI-configurable
Status: current

SOCKS5 proxy support is built in. Current session-state defaults enable proxy at `127.0.0.1:1080`; proxy credentials are optional.

## D-007 — Local tags are not written to Telegram
Status: current

Tags are application metadata stored in SQLite only.

## D-008 — Search/filter is mostly local
Status: current

The application fetches a bounded Telegram history set and then applies text search, date checks, and tag filtering locally in the Streamlit process.

## D-009 — Remember-me uses opaque bearer token + server-side hash
Status: current

The raw random token is kept in the browser cookie. Only SHA-256(token) and expiry are stored server-side.

## D-010 — Branch `others` is a modular reimplementation
Status: current

Compared with `main`, this branch significantly shrinks `app.py` and separates configuration, persistence, Telegram services/runtime, UI, and utilities. Future changes should preserve this separation unless a redesign is explicitly requested.

## D-011 — Media is downloaded lazily
Status: current

Telegram message listing carries metadata only. Full media bytes are fetched only after an explicit user action such as photo preview, video playback, or video-download preparation.

Downloaded media is stored in a bounded local cache scoped by Web-selected Telegram account, chat, and message. Cache TTL, total size, preview size, and download size are configurable. Video browser downloads use the cached file and keep the Telegram-facing download separate from the browser-facing download control.
