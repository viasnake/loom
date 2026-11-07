import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from loom.storage import (AppPaths, CorruptSaveError, FutureVersionError,
                          MigrationError, SaveError, SaveStore)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = SaveStore(self.root)

    def test_unicode_roundtrip_and_previous_backup(self):
        self.store.save({"name": "ゲーム", "score": 1})
        first = self.store.path().read_bytes()
        self.store.save({"score": 2})
        self.assertEqual(self.store.load(), {"score": 2})
        self.assertEqual((self.root / "main.json.bak").read_bytes(), first)

    def test_load_missing_does_not_create_directory(self):
        store = SaveStore(self.root / "absent")
        with self.assertRaises(FileNotFoundError):
            store.load()
        self.assertFalse(store.root.exists())

    def test_migration_is_in_memory_and_save_retains_original(self):
        self.store.save({"points": 7})
        original = self.store.path().read_bytes()
        new = SaveStore(self.root, version=3, migrations={
            1: lambda old: {"score": old["points"]},
            2: lambda old: {**old, "level": 1},
        })
        self.assertEqual(new.load(), {"score": 7, "level": 1})
        self.assertEqual(self.store.path().read_bytes(), original)
        new.save(new.load())
        self.assertEqual((self.root / "main.json.bak").read_bytes(), original)
        with self.assertRaises(FutureVersionError):
            self.store.load()
        with self.assertRaises(FutureVersionError):
            self.store.save({})

    def test_missing_and_failed_migration_never_overwrite(self):
        self.store.save({"score": 1})
        original = self.store.path().read_bytes()
        for migrations in ({}, {1: lambda _: None}, {1: lambda _: {"value": float("nan")}}):
            store = SaveStore(self.root, version=2, migrations=migrations)
            with self.assertRaises(MigrationError):
                store.load()
            with self.assertRaises(MigrationError):
                store.save({})
            self.assertEqual(store.path().read_bytes(), original)

    def test_corruption_blocks_save_until_explicit_recovery(self):
        self.store.save({"score": 1})
        self.store.save({"score": 2})
        self.store.path().write_bytes(b"broken")
        with self.assertRaises(CorruptSaveError):
            self.store.save({"score": 3})
        self.assertEqual(self.store.recover(), {"score": 1})
        self.assertEqual(self.store.load(), {"score": 1})
        self.assertEqual((self.root / "main.json.rejected").read_bytes(), b"broken")

    def test_recovery_of_missing_primary(self):
        self.store.save({"score": 1})
        self.store.save({"score": 2})
        self.store.path().unlink()
        self.assertEqual(self.store.recover(), {"score": 1})

    def test_recovery_refuses_valid_or_future_primary(self):
        self.store.save({"score": 1})
        self.store.save({"score": 2})
        with self.assertRaises(SaveError):
            self.store.recover()
        future = SaveStore(self.root, version=2, migrations={1: lambda data: data})
        future.save({"score": 3})
        original = future.path().read_bytes()
        with self.assertRaises(FutureVersionError):
            self.store.recover()
        self.assertEqual(future.path().read_bytes(), original)

    def test_invalid_backup_does_not_touch_corrupt_primary(self):
        self.store.path().write_bytes(b"primary")
        (self.root / "main.json.bak").write_bytes(b"backup")
        with self.assertRaises(CorruptSaveError):
            self.store.recover()
        self.assertEqual(self.store.path().read_bytes(), b"primary")

    def test_primary_replace_failure_retains_valid_save_and_cleans_temp(self):
        self.store.save({"score": 1})
        original = self.store.path().read_bytes()
        replace = os.replace
        def fail_primary(source, target):
            if Path(target) == self.store.path():
                raise OSError("simulated disk error")
            replace(source, target)
        with patch("loom.storage.os.replace", side_effect=fail_primary):
            with self.assertRaises(OSError):
                self.store.save({"score": 2})
        self.assertEqual(self.store.path().read_bytes(), original)
        self.assertEqual((self.root / "main.json.bak").read_bytes(), original)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_backup_failure_does_not_change_primary(self):
        self.store.save({"score": 1})
        original = self.store.path().read_bytes()
        with patch("loom.storage.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.save({"score": 2})
        self.assertEqual(self.store.path().read_bytes(), original)

    def test_serialization_failure_leaves_files_untouched(self):
        self.store.save({"score": 1})
        original = self.store.path().read_bytes()
        for bad in ({"x": float("nan")}, {1: "coerced"}, {"x": object()}, []):
            with self.assertRaises((ValueError, TypeError)):
                self.store.save(bad)
            self.assertEqual(self.store.path().read_bytes(), original)
            self.assertFalse((self.root / "main.json.bak").exists())

    def test_invalid_envelopes(self):
        for raw in (b"[]", b'{}', b'\xff',
                    b'{"format":"loom.save","version":true,"data":{}}',
                    b'{"format":"loom.save","version":1,"data":{"x":NaN}}',
                    b'{"format":"loom.save","version":1,"data":{"x":1,"x":2}}'):
            self.store.path().write_bytes(raw)
            with self.assertRaises(CorruptSaveError):
                self.store.load()

    def test_invalid_names_and_versions(self):
        for name in ("", "../x", "/tmp/x", "a/b", "a\\b", "foo.", "CON", "nul.json", "COM1", "a\x00b"):
            with self.assertRaises(ValueError):
                self.store.path(name)
        for version in (0, -1, True, "1"):
            with self.assertRaises(ValueError):
                SaveStore(self.root, version=version)

    def test_symlink_primary_and_backup_refused(self):
        external = self.root / "external"
        external.write_text("untouched")
        try:
            self.store.path().symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        with self.assertRaises(SaveError):
            self.store.save({})
        self.store.path().unlink()
        self.store.save({})
        (self.root / "main.json.bak").symlink_to(external)
        with self.assertRaises(SaveError):
            self.store.save({"next": True})
        self.assertEqual(external.read_text(), "untouched")

    def test_os_paths_separate_settings_and_progress(self):
        # Use host-absolute paths even when exercising another platform branch.
        data, config = self.root / "data", self.root / "config"
        roaming, local = self.root / "roaming", self.root / "local"
        with patch("loom.storage.sys.platform", "linux"), patch.dict(os.environ, {
                "XDG_DATA_HOME": str(data), "XDG_CONFIG_HOME": str(config)}):
            paths = AppPaths.for_app("com.example.game")
            self.assertEqual(paths.progress, data / "com.example.game/saves")
            self.assertEqual(paths.settings, config / "com.example.game/settings")
            self.assertEqual(SaveStore.for_app("com.example.game").root, paths.progress)
        with patch("loom.storage.sys.platform", "win32"), patch.dict(os.environ, {
                "APPDATA": str(roaming), "LOCALAPPDATA": str(local)}):
            paths = AppPaths.for_app("com.example.game")
            self.assertEqual(paths.progress, roaming / "com.example.game/saves")
            self.assertEqual(paths.settings, local / "com.example.game/settings")
        with patch("loom.storage.sys.platform", "linux"), patch.dict(os.environ, {
                "XDG_DATA_HOME": "relative", "XDG_CONFIG_HOME": "relative"}):
            paths = AppPaths.for_app("game")
            self.assertTrue(paths.progress.is_absolute())
            self.assertTrue(paths.settings.is_absolute())
        with patch("loom.storage.sys.platform", "darwin"):
            paths = AppPaths.for_app("game")
            self.assertNotEqual(paths.progress, paths.settings)
            self.assertIn("Application Support", str(paths.progress))
        with self.assertRaises(ValueError):
            SaveStore.for_app("valid", kind="invalid")


if __name__ == "__main__":
    unittest.main()
