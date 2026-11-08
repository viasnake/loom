"""Fast checks for the standalone harness; building is a separate CI job."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "check_bundle", Path(__file__).resolve().parents[1] / "tools/check_bundle.py"
)
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class BundleToolTests(unittest.TestCase):
    def test_probe_environment_drops_python_injection(self):
        with patch.dict(
            os.environ,
            {
                "PYTHONPATH": "source",
                "PYTHONHOME": "home",
                "VIRTUAL_ENV": "venv",
                "PATH": "development-venv",
            },
        ):
            env = bundle.probe_environment(Path("out"), Path("saves"))
            for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
                self.assertNotIn(key, env)
            self.assertNotIn("development-venv", env["PATH"])
            self.assertEqual(os.environ["PYTHONPATH"], "source")

    def test_frozen_lifecycle_resource_and_save_evidence_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            executable = base / "build/relocated/probe/probe"
            root = base / "source"
            report = {
                "frozen": True,
                "runs": 2,
                "pixel": 8,
                "rendered_pixel": 8,
                "executable": str(executable),
                "bundle_root": str(executable.parent / "_internal"),
                "pyxel_origin": str(executable.parent / "_internal/pyxel/__init__.py"),
                "loom_origin": str(base / "extracted/loom/__init__.py"),
                "game_origin": str(base / "extracted/main.py"),
                "asset_origin": str(base / "extracted/assets/pixel.png"),
                "events": [
                    "start.enter",
                    "start.update",
                    "start.exit",
                    "finish.enter",
                    "finish.update",
                    "finish.exit",
                ],
            }
            bundle.validate_report(report, 2, executable, root)
            for key, bad in (
                ("frozen", False),
                ("runs", 1),
                ("pixel", 0),
                ("bundle_root", str(base / "some-other-bundle")),
                ("rendered_pixel", 0),
                ("events", []),
                ("executable", str(base / "python")),
                ("pyxel_origin", str(base / "site-packages/pyxel.py")),
                ("loom_origin", str(root / "src/loom/__init__.py")),
            ):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    bundle.validate_report({**report, key: bad}, 2, executable, root)

    def test_resource_is_a_real_png(self):
        data = bundle.png_pixel()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIn(b"IHDR", data)
        self.assertIn(b"IDAT", data)
        self.assertIn(b"IEND", data)
