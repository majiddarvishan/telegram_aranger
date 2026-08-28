# Telegram Saved Messages Manager

A Streamlit multi-user Telegram archive manager using Pyrogram. No Keycloak is used.

## Features

- Local multi-user web authentication with PBKDF2 password hashing.
- Multiple Telegram accounts per web user.
- Telegram phone login, verification code, and Telegram 2FA.
- Encrypted Telegram session strings using Fernet.
- Telegram logout and non-destructive disconnect.
- Chat selector for private chats, groups, supergroups, and channels.
- Date-range message filtering; defaults to the latest 7 calendar days.
- Previous/Next Day navigation at the bottom of the page.
- Search and per-message tags.
- SQLite persistence.
- Dedicated asyncio runtime thread for Pyrogram.
- Python 3.14 import compatibility workaround.
- SOCKS5 proxy support.

## Project layout

```text
telegram_saved_manager/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── config/
│   └── settings.py
├── db/
│   ├── database.py
│   ├── users.py
│   ├── telegram_accounts.py
│   └── tags.py
├── services/
│   ├── telegram_runtime.py
│   └── telegram_service.py
├── ui/
│   ├── auth.py
│   ├── sidebar.py
│   └── main.py
└── utils/
    ├── state.py
    └── date_range.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and a valid Fernet key.

Generate the Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

4. Start:

```bash
streamlit run app.py
```

## Important

Telegram sessions are encrypted at rest with the Fernet key. Keep `TELEGRAM_SESSION_ENCRYPTION_KEY` secret and back it up securely. Losing it makes stored Telegram sessions undecryptable.

The application deliberately does not use Keycloak.
