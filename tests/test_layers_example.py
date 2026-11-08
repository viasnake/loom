"""The font-aware sample composes UI actions with game state, not just rendering."""

import importlib.util
from pathlib import Path
import unittest

from loom import InputFrame, SceneStack


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class LayersExampleTests(unittest.TestCase):
    def test_pause_button_changes_label_and_controls_world_updates(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "layers.py"
        spec = importlib.util.spec_from_file_location("layers_example", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        scene = module.Layers()
        quit_requests = []
        stack = SceneStack(scene, lambda: quit_requests.append(True))
        try:
            stack.update(InputFrame(pressed=frozenset({"next"})), 0)
            stack.update(InputFrame(pressed=frozenset({"confirm"})), 1)
            self.assertEqual(scene.toggle.text, "Resume")
            self.assertEqual(scene.angle, 0)
            stack.update(InputFrame(held=frozenset({"confirm"})), 1)
            self.assertEqual(scene.angle, 0)
            stack.update(InputFrame(pressed=frozenset({"confirm"})), 1)
            self.assertEqual(scene.toggle.text, "Pause")
            self.assertEqual(scene.angle, 40)
            stack.update(InputFrame(pressed=frozenset({"cancel"})), 0)
            self.assertEqual(quit_requests, [True])
        finally:
            stack.close()
