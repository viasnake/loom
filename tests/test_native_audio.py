"""Exercise real Pyxel channel state without claiming speaker/auditory testing."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeAudioTests(unittest.TestCase):
    def test_gain_composition_voice_reuse_and_unowned_channel_isolation(self):
        script = """
import json
import pyxel
from loom.audio import AudioMixer
pyxel.init(32, 32, headless=True)
pyxel.sounds[0].set("c3e3g3", "p", "5", "n", 8)
baseline = [pyxel.channels[i].gain for i in range(4)]
pyxel.channels[3].play(0, loop=True)
mixer = AudioMixer(channels=pyxel.channels, buses={"music": (0,), "sfx": (1,)})
mixer.master_volume = 0.5
mixer.set_bus_volume("sfx", 0.4)
composed = pyxel.channels[1].gain
first = mixer.play("sfx", 0, loop=True)
full = mixer.play("sfx", 0) is None
first.stop()
second = mixer.play("sfx", 0, loop=True)
first.stop()
reused_active = second.active
mixer.set_bus_muted("sfx", True)
muted = pyxel.channels[1].gain
still_playing = second.active
mixer.close()
print("AUDIO:" + json.dumps({
    "baseline": baseline, "composed": composed, "full": full,
    "reused_active": reused_active, "muted": muted,
    "still_playing": still_playing, "closed_voice": second.active,
    "restored": [pyxel.channels[i].gain for i in range(4)],
    "owned_stopped": pyxel.channels[1].play_pos() is None,
    "unowned_playing": pyxel.channels[3].play_pos() is not None,
}))
pyxel.channels[3].stop()
"""
        environment = os.environ.copy()
        environment["SDL_AUDIODRIVER"] = "dummy"
        source = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONPATH"] = os.pathsep.join(
            [source, environment.get("PYTHONPATH", "")]
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=20,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        reports = [
            line[6:] for line in result.stdout.splitlines() if line.startswith("AUDIO:")
        ]
        self.assertEqual(len(reports), 1, result.stdout + result.stderr)
        report = json.loads(reports[0])
        self.assertAlmostEqual(report["composed"], report["baseline"][1] * 0.5 * 0.4)
        for key in (
            "full",
            "reused_active",
            "still_playing",
            "owned_stopped",
            "unowned_playing",
        ):
            self.assertTrue(report[key], key)
        self.assertEqual(report["muted"], 0)
        self.assertFalse(report["closed_voice"])
        self.assertEqual(report["restored"], report["baseline"])
