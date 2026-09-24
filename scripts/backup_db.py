import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def key_fingerprint(key: str | None) -> str | None:
    if not key:
        return None
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def schema_version(db_file: str) -> int:
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute(
            """
            SELECT value
            FROM schema_meta
            WHERE key='schema_version'
            """
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def create_backup(
    db_file: str,
    output_dir: str,
    encryption_key: str | None = None,
) -> Path:
    source_path = Path(db_file)
    if not source_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {source_path}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(output_dir) / f"telegram-backup-{stamp}"
    suffix = 1
    while backup_dir.exists():
        backup_dir = Path(output_dir) / f"telegram-backup-{stamp}-{suffix}"
        suffix += 1
    backup_dir.mkdir(parents=True)

    backup_db = backup_dir / "database.sqlite3"
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(backup_db)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": schema_version(str(backup_db)),
        "fernet_key_sha256": key_fingerprint(encryption_key),
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return backup_dir


def main():
    parser = argparse.ArgumentParser(
        description="Create a consistent SQLite backup for telegram_aranger."
    )
    parser.add_argument("--db", default="telegram_manager.db")
    parser.add_argument("--output-dir", default="backups")
    args = parser.parse_args()

    backup_dir = create_backup(
        args.db,
        args.output_dir,
        os.getenv("TELEGRAM_SESSION_ENCRYPTION_KEY"),
    )
    print(backup_dir)


if __name__ == "__main__":
    main()
