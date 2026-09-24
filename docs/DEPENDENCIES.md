# Dependency Policy

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
- TgCrypto
- cryptography
- python-dotenv
- extra-streamlit-components

For bounded dependencies:
- review updates at least monthly;
- apply patch/minor updates first in `feature/media-support` or a dedicated dependency branch;
- require CI to pass;
- manually verify Web login, remember-me, Telegram restore, and media UI before merge.

## TgCrypto

This repository currently installs `TgCrypto` from `requirements.txt`, so **for this application it is an installed dependency**, not an optional installation step.

Upstream Pyrogram can operate without TgCrypto using slower pure-Python cryptographic operations, but that is not the deployment profile represented by this repository's requirements file.

## Security review

Because Pyrogram upstream is archived, dependency review must include:
- Telegram API compatibility risk;
- unresolved upstream security issues;
- Python-version compatibility;
- maintained fork/replacement options.

Do not silently switch Telegram client libraries merely to receive updates. Session migration and behavior compatibility must be designed and tested explicitly.
