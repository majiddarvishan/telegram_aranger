# Backup and Restore

## What must be protected together

A usable backup requires both:
1. the SQLite database;
2. the exact `TELEGRAM_SESSION_ENCRYPTION_KEY` that can decrypt stored Telegram session strings.

The key should **not** be copied into the same ordinary backup archive as the database. Store it in a secret manager or separately protected backup. The backup helper writes only a SHA-256 fingerprint so restore can verify that the supplied key matches the database backup without storing the key itself.

## Create a database backup

With the application environment loaded:

```bash
python scripts/backup_db.py --db telegram_manager.db --output-dir backups
```

The helper uses SQLite's online backup API rather than copying the live database/WAL files directly.

It creates a timestamped directory containing:
- `database.sqlite3`
- `manifest.json`

The manifest records:
- UTC backup time;
- schema version;
- Fernet-key fingerprint when the key is available.

Back up the Fernet key separately in your secret-management system at the same time.

## Restore

Stop the application first so no new writes occur.

Ensure `TELEGRAM_SESSION_ENCRYPTION_KEY` contains the key paired with the backup, then run:

```bash
python scripts/restore_db.py \
  --backup-dir backups/telegram-backup-YYYYMMDDTHHMMSSZ \
  --db telegram_manager.db
```

If the destination already exists, restore refuses by default. Use `--force` only after you have a separate rollback copy; the script renames the existing database before restoring.

If a key fingerprint is present in the manifest and the configured key does not match, restore aborts.

## Verification after restore

1. Start the application.
2. Confirm schema initialization completes.
3. Confirm local Web login works.
4. Confirm remembered login behavior if expected.
5. Restore each saved Telegram account and verify `get_me()` succeeds.
6. Open at least two chats and verify tags remain isolated by chat.
7. Confirm media can be downloaded to a fresh cache.

Do not retire the previous database/key backup until these checks pass.
