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


def restore_backup(
    backup_dir: str,
    db_file: str,
    encryption_key: str | None,
    force: bool = False,
) -> Path:
    source_dir = Path(backup_dir)
    source_db = source_dir / "database.sqlite3"
    manifest_path = source_dir / "manifest.json"

    if not source_db.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(
            "Backup directory must contain database.sqlite3 and manifest.json."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_fingerprint = manifest.get("fernet_key_sha256")
    if expected_fingerprint:
        actual_fingerprint = key_fingerprint(encryption_key)
        if actual_fingerprint != expected_fingerprint:
            raise RuntimeError(
                "TELEGRAM_SESSION_ENCRYPTION_KEY does not match this backup."
            )

    destination_path = Path(db_file)
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    if destination_path.exists():
        if not force:
            raise FileExistsError(
                f"Destination already exists: {destination_path}. "
                "Use --force only after taking a rollback backup."
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        rollback = destination_path.with_name(
            f"{destination_path.name}.pre-restore-{stamp}.bak"
        )
        destination_path.replace(rollback)

    source = sqlite3.connect(source_db)
    destination = sqlite3.connect(destination_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    return destination_path


def main():
    parser = argparse.ArgumentParser(
        description="Restore a telegram_aranger SQLite backup."
    )
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--db", default="telegram_manager.db")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    restored = restore_backup(
        args.backup_dir,
        args.db,
        os.getenv("TELEGRAM_SESSION_ENCRYPTION_KEY"),
        force=args.force,
    )
    print(restored)


if __name__ == "__main__":
    main()
