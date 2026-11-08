"""Subprocess regression tests for Pyxel operations that can exit the interpreter."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeRuntimeTests(unittest.TestCase):
    def test_resize_is_deferred_and_quit_runs_cleanup(self):
        fixture = Path(__file__).with_name("fixtures") / "runtime_contract.py"
        environment = os.environ.copy()
        environment["SDL_AUDIODRIVER"] = "dummy"
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = os.pathsep.join(
            [source, environment.get("PYTHONPATH", "")]
        )
        result = subprocess.run(
            [sys.executable, str(fixture)],
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = [
            line.removeprefix("CONTRACT:")
            for line in result.stdout.splitlines()
            if line.startswith("CONTRACT:")
        ]
        # Native quit may exit without returning from run(). Only the exit hook
        # can produce this report, so a successful process alone is insufficient.
        self.assertEqual(len(reports), 1, result.stdout + result.stderr)
        report = json.loads(reports[0])
        self.assertEqual(report["before_request"], [24, 18])
        self.assertEqual(report["after_request"], [24, 18])
        self.assertEqual(report["draw_size"], [42, 30])
        self.assertEqual(report["draw_pixels"], [2, 2])
        self.assertEqual(report["update_sizes"], [[24, 18], [42, 30]])
        self.assertEqual(report["exit_count"], 1)
