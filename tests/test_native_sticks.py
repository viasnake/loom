"""Exercise the native Pyxel analog boundary, not a physical controller."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeStickTests(unittest.TestCase):
    def test_signed_values_deadzone_and_cancel_use_native_analog_polling(self):
        script = """
import math
import pyxel
from loom import ActionMap, StickBinding

pyxel.init(16, 16, headless=True)
x, y = pyxel.GAMEPAD1_AXIS_LEFTX, pyxel.GAMEPAD1_AXIS_LEFTY
actions = ActionMap({}, sticks={"move": StickBinding(x, y)})
def sample(a, b):
    pyxel.set_btnv(x, a)
    pyxel.set_btnv(y, b)
    return actions.sample(pyxel.btn, axis_value=pyxel.btnv)
assert sample(100, -100).sticks["move"] == (0, 0)
assert sample(-32768, 0).sticks["move"] == (-1, 0)
assert sample(32767, 0).sticks["move"] == (1, 0)
assert sample(100000, 0).sticks["move"] == (1, 0)
v = sample(32767, 32767).sticks["move"]
assert math.isclose(math.hypot(*v), 1)
actions.cancel()
f = sample(32767, 0)
assert f.sticks["move"] == (0, 0) and "move" in f.cancelled
assert "move" not in f.released
assert sample(32767, 0).sticks["move"] == (0, 0)
assert sample(0, 0).sticks["move"] == (0, 0)
assert sample(32767, 0).sticks["move"] == (1, 0)
print("native analog assertions passed")
"""
        environment = os.environ.copy()
        environment["SDL_AUDIODRIVER"] = "dummy"
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = os.pathsep.join(
            [source, environment.get("PYTHONPATH", "")]
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=environment,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("native analog assertions passed", result.stdout)
