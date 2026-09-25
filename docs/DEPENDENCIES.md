# Telegram Harbor Dependency Policy

## Update policy

Dependencies fall into two groups:

### Deliberately pinned
- `pyrogram==2.0.106`

Pyrogram is pinned because it is the core Telegram protocol dependency and changes can affect authentication, exported sessions, message parsing, and media transfer behavior.

The upstream Pyrogram repository was archived by its owner on 2024-12-23 and is no longer maintained or supported. Treat this as a long-term maintenance risk.

Before replacing Pyrogram or moving to a fork:
1. verify exported-session compatibility;
2. test login/code/2FA flows;
3. test account restore;
4. test history/date offsets;
5. test photo/video metadata and download progress;
6. run the complete regression suite;
7. test against a real non-production Telegram account.

### Bounded ranges
- Streamlit
- tgcrypto2
- cryptography
- python-dotenv
- extra-streamlit-components
- yt-dlp

For bounded dependencies:
- review updates at least monthly;
- apply patch/minor updates first in a dedicated dependency branch from `main`;
- require CI to pass;
- manually verify Web login, remember-me, Telegram restore, and media UI before merge.

## Telegram crypto acceleration

Telegram Harbor installs `tgcrypto2>=1.3.6,<2`.

`tgcrypto2` is a maintained fork of the archived original `TgCrypto` project. Its PyPI package name is `tgcrypto2`, but it intentionally keeps the Python import name `tgcrypto` for drop-in compatibility with Pyrogram.

Why this project uses it:
- the original `TgCrypto 1.2.5` Windows wheels stop at older CPython versions and can be missing on modern Windows/Python environments;
- `tgcrypto2` provides modern wheels, including Windows CPython 3.14;
- Pyrogram can continue using `import tgcrypto` without source changes;
- without a usable `tgcrypto` module, Pyrogram falls back to significantly slower pure-Python crypto.

Windows/Python 3.14 compatibility is explicitly validated in GitHub Actions.

## Security review

Because Pyrogram upstream is archived, dependency review must include:
- Telegram API compatibility risk;
- unresolved upstream security issues;
- Python-version compatibility;
- maintained fork/replacement options.

Do not silently switch Telegram client libraries merely to receive updates. Session migration and behavior compatibility must be designed and tested explicitly.


## YouTube downloader and FFmpeg

Telegram Harbor uses `yt-dlp` only behind the YouTube service abstraction. Streamlit UI code must not depend on yt-dlp internals.

The Python dependency is kept inside the bounded 2026 major range in `requirements.txt`. Downloader updates can change extractor behavior, metadata fields, format selection and error text, so update it through the normal dependency-review flow and run the YouTube service/download regression suite.

FFmpeg and FFprobe are operational dependencies for:
- merging video and audio streams;
- audio-only extraction;
- subtitle conversion to SRT where supported.

The Docker image installs FFmpeg directly. Native Windows/Linux installations must provide `ffmpeg` and `ffprobe` on `PATH`.


## YouTube browser-session authentication

Browser-session authentication uses yt-dlp's `cookies-from-browser` integration and therefore depends on the browser profile and OS credential store being readable by the Telegram Harbor process.

Operational requirements:
- Telegram Harbor and the selected browser profile must be on the same host.
- Run Telegram Harbor under the same OS user that owns/decrypts the browser cookies.
- Chromium-family cookies may depend on the platform credential store (for example Windows DPAPI or a Linux desktop keyring).
- Firefox requires access to its local profile/cookie database.
- Containers normally cannot access/decrypt the desktop browser profile unless it is deliberately mounted with the necessary host credentials; use the `cookies.txt` fallback instead.
- Browser cookie extraction behavior is provided by the installed yt-dlp version; keep yt-dlp within the project's pinned supported range.

If browser extraction fails, Telegram Harbor normalizes the error as `youtube_browser_session_unavailable` without displaying raw cookie/database paths.
