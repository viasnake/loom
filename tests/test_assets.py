import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from loom.assets import AssetStore


class AssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "assets"
        self.root.mkdir()
        (self.root / "nested").mkdir()
        (self.root / "nested" / "text.txt").write_text("hello", encoding="utf8")

    def test_filesystem_anchor_survives_cwd_change(self):
        previous = Path.cwd()
        try:
            os.chdir(self.base)
            store = AssetStore("assets")
            os.chdir(self.base.parent)
            path = store.path("nested/text.txt")
            self.assertEqual(path, self.root / "nested" / "text.txt")
            self.assertEqual(path.read_text(), "hello")
            self.assertEqual(Path.cwd(), self.base.parent)
            store.close()
            self.assertTrue(path.exists())
        finally:
            os.chdir(previous)

    def test_bad_relative_names_rejected_without_changing_store(self):
        with AssetStore(self.root) as store:
            for name in (
                "",
                "/",
                "/tmp/a",
                "../a",
                "nested/../text.txt",
                "./a",
                "a//b",
                "a/",
                r"a\b",
                r"C:\a",
                "C:a",
                "a\x00b",
            ):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    store.path(name)
            with self.assertRaises(TypeError):
                store.path(Path("nested/text.txt"))
            self.assertEqual(store.path("nested/text.txt").read_text(), "hello")

    def test_missing_directory_and_closed_lifetimes(self):
        with self.assertRaises(FileNotFoundError):
            AssetStore(self.base / "missing")
        with self.assertRaises(NotADirectoryError):
            AssetStore(self.root / "nested" / "text.txt")
        store = AssetStore(self.root)
        with self.assertRaises(IsADirectoryError):
            store.path("nested")
        with self.assertRaises(FileNotFoundError):
            store.path("missing")
        store.close()
        store.close()
        self.assertTrue(store.closed)
        with self.assertRaises(RuntimeError):
            store.path("nested/text.txt")
        with self.assertRaises(RuntimeError):
            store.__enter__()

    def test_symlink_file_and_directory_escape_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("outside")
        try:
            (self.root / "out").symlink_to(outside, target_is_directory=True)
            (self.root / "file.txt").symlink_to(outside / "secret.txt")
            (self.root / "inside.txt").symlink_to(self.root / "nested" / "text.txt")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with AssetStore(self.root) as store:
            for name in ("out/secret.txt", "file.txt"):
                with self.assertRaises(ValueError):
                    store.path(name)
            self.assertEqual(store.path("inside.txt").read_text(), "hello")

    def _load_package(self, name, location):
        sys.path.insert(0, str(location))
        importlib.invalidate_caches()

        def cleanup():
            sys.modules.pop(name, None)
            sys.path.remove(str(location))
            sys.path_importer_cache.pop(str(location), None)
            importlib.invalidate_caches()

        self.addCleanup(cleanup)
        return importlib.import_module(name)

    def _zip_package(self):
        name = "_loom_assets_zip_test"
        archive = self.base / "package.zip"
        with zipfile.ZipFile(archive, "w") as target:
            target.writestr(f"{name}/__init__.py", "")
            target.writestr(f"{name}/data/text.txt", "zip hello")
            target.writestr(f"{name}/data/other.bin", b"\x00\xff")
        return self._load_package(name, archive)

    def test_zip_materialization_cached_until_close(self):
        package = self._zip_package()
        with AssetStore.from_package(package, "data") as store:
            first = store.path("text.txt")
            self.assertIs(store.path("text.txt"), first)
            self.assertEqual(first.read_text(), "zip hello")
            second = store.path("other.bin")
            self.assertEqual(second.read_bytes(), b"\x00\xff")
            self.assertTrue(first.is_absolute())
        self.assertFalse(first.exists() or second.exists())
        with self.assertRaises(RuntimeError):
            store.path("text.txt")

    def test_zip_context_cleans_on_exception(self):
        package = self._zip_package()
        with self.assertRaisesRegex(RuntimeError, "body"):
            with AssetStore.from_package(package) as store:
                path = store.path("data/text.txt")
                raise RuntimeError("body")
        self.assertFalse(path.exists())

    def test_package_names_and_missing_members(self):
        package = self._zip_package()
        for directory in ("../data", "/data", r"data\a", "data/"):
            with self.assertRaises(ValueError):
                AssetStore.from_package(package, directory)
        with self.assertRaises(NotADirectoryError):
            AssetStore.from_package(package, "data/text.txt")
        with AssetStore.from_package(package) as store:
            with self.assertRaises(IsADirectoryError):
                store.path("data")
            with self.assertRaises(FileNotFoundError):
                store.path("missing")
            self.assertEqual(store.path("data/text.txt").read_text(), "zip hello")

    def test_directory_package_anchors_and_rejects_symlink_directory_escape(self):
        name = "_loom_assets_dir_test"
        package_dir = self.base / name
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("")
        (package_dir / "data").mkdir()
        (package_dir / "data" / "file.txt").write_text("directory")
        package = self._load_package(name, self.base)
        with AssetStore.from_package(package, "data") as store:
            path = store.path("file.txt")
            self.assertEqual(path, package_dir / "data" / "file.txt")
        self.assertTrue(path.exists())
        try:
            (package_dir / "escape").symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(ValueError):
            AssetStore.from_package(package, "escape")

    def test_custom_resource_loader_rejected(self):
        with patch("loom.assets.resources.files", return_value=object()):
            with self.assertRaises(TypeError):
                AssetStore.from_package("anything")

    def test_materialization_failure_does_not_poison_cache(self):
        package = self._zip_package()
        with AssetStore.from_package(package, "data") as store:
            with patch("loom.assets.resources.as_file", side_effect=OSError("extract")):
                with self.assertRaises(OSError):
                    store.path("text.txt")
            path = store.path("text.txt")
            self.assertEqual(path.read_text(), "zip hello")
        self.assertFalse(path.exists())
