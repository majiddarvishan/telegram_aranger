import json
import tempfile
import unittest
from pathlib import Path

from db.database import get_db, initialize_database
from db.users import create_user
from scripts.backup_db import create_backup, key_fingerprint
from scripts.restore_db import restore_backup


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_file = self.root / "telegram.db"
        initialize_database(str(self.db_file))
        create_user(str(self.db_file), "alice", "password123", "Alice")

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_manifest_binds_database_to_key_without_storing_key(self):
        key = "test-fernet-key-material"
        backup_dir = create_backup(
            str(self.db_file),
            str(self.root / "backups"),
            key,
        )

        manifest_text = (backup_dir / "manifest.json").read_text(
            encoding="utf-8"
        )
        manifest = json.loads(manifest_text)

        self.assertTrue((backup_dir / "database.sqlite3").is_file())
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["fernet_key_sha256"], key_fingerprint(key))
        self.assertNotIn(key, manifest_text)

    def test_restore_recreates_database_and_preserves_rows(self):
        key = "test-fernet-key-material"
        backup_dir = create_backup(
            str(self.db_file),
            str(self.root / "backups"),
            key,
        )
        restored_db = self.root / "restored.db"

        restore_backup(
            str(backup_dir),
            str(restored_db),
            key,
        )

        conn = get_db(str(restored_db))
        try:
            row = conn.execute(
                "SELECT username, display_name FROM users"
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row, ("alice", "Alice"))

    def test_restore_rejects_wrong_encryption_key(self):
        backup_dir = create_backup(
            str(self.db_file),
            str(self.root / "backups"),
            "correct-key",
        )

        with self.assertRaisesRegex(RuntimeError, "does not match"):
            restore_backup(
                str(backup_dir),
                str(self.root / "restored.db"),
                "wrong-key",
            )

    def test_restore_refuses_overwrite_without_force(self):
        backup_dir = create_backup(
            str(self.db_file),
            str(self.root / "backups"),
            "key",
        )

        with self.assertRaises(FileExistsError):
            restore_backup(
                str(backup_dir),
                str(self.db_file),
                "key",
            )


if __name__ == "__main__":
    unittest.main()
