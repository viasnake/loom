"""Load real PNG assets through native Pyxel despite cwd and package layout."""

import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
import zlib


def red_pixel_png():
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x4d"))
        + chunk(b"IEND", b"")
    )


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeAssetTests(unittest.TestCase):
    def test_native_image_load_from_anchored_directory_and_zip(self):
        script = """
import json
from pathlib import Path
import sys
import pyxel
from loom.assets import AssetStore
before = Path.cwd()
assets = AssetStore("assets")
sys.path.insert(0, sys.argv[1])
packaged = AssetStore.from_package("loom_native_fixture", directory="assets")
pyxel.init(32, 32, headless=True)
local = assets.path("dot.png")
extracted = packaged.path("dot.png")
image = pyxel.Image(1, 1)
image.load(0, 0, str(local))
local_color = image.pget(0, 0)
image.load(0, 0, str(extracted))
zip_color = image.pget(0, 0)
cached = extracted == packaged.path("dot.png")
packaged.close()
assets.close()
print("ASSETS:" + json.dumps({
    "cwd_changed": before != Path.cwd(), "local_color": local_color,
    "zip_color": zip_color, "cache": cached,
    "extraction_removed": not extracted.exists(), "local_preserved": local.exists(),
}))
"""
        with TemporaryDirectory() as directory:
            root = Path(directory)
            launch = root / "launch"
            (launch / "assets").mkdir(parents=True)
            (launch / "assets" / "dot.png").write_bytes(red_pixel_png())
            runner = root / "runner"
            runner.mkdir()
            entry = runner / "check.py"
            entry.write_text(script, encoding="utf-8")
            archive = root / "resources.zip"
            with ZipFile(archive, "w") as bundle:
                bundle.writestr("loom_native_fixture/__init__.py", "")
                bundle.writestr("loom_native_fixture/assets/dot.png", red_pixel_png())
            environment = os.environ.copy()
            environment["SDL_AUDIODRIVER"] = "dummy"
            source = str(Path(__file__).resolve().parents[1] / "src")
            environment["PYTHONPATH"] = os.pathsep.join(
                [source, environment.get("PYTHONPATH", "")]
            )
            result = subprocess.run(
                [sys.executable, str(entry), str(archive)],
                cwd=launch,
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = [
            line[7:]
            for line in result.stdout.splitlines()
            if line.startswith("ASSETS:")
        ]
        self.assertEqual(len(reports), 1, result.stdout + result.stderr)
        report = json.loads(reports[0])
        for name in ("cwd_changed", "cache", "extraction_removed", "local_preserved"):
            self.assertTrue(report[name], name)
        self.assertEqual(report["local_color"], 8)
        self.assertEqual(report["zip_color"], 8)
