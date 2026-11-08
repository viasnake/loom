"""Pixel evidence for sprite frame selection and existing camera composition."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeSpriteTests(unittest.TestCase):
    def test_selected_regions_are_drawn_inside_camera_and_composited(self):
        script = """
import pyxel
from loom import Camera2D, CameraView, DisplayConfig, SpriteClip, SpritePlayer
from loom.display import PyxelDisplay
pyxel.init(80,60,headless=True)
sheet=pyxel.Image(6,2)
for i,color in enumerate((7,8,9)):
    sheet.rect(i*2,0,2,2,color)
player=SpritePlayer(SpriteClip(((0,0,2,2),(2,0,2,2),(4,0,2,2)),fps=4),loop=False)
display=PyxelDisplay(pyxel,DisplayConfig(output_size=(80,60),world_size=(20,10)))
camera=Camera2D((20,10),position=(3,2))
view=CameraView(display.world)
for color in (7,8,9):
    display.world.cls(0)
    with view.apply(camera) as image:
        image.blt(5,4,sheet,*player.frame)
    assert display.world.pget(2,2)==color
    assert display.world.pget(3,3)==color
    assert display.world.pget(1,2)==0
    display.composite()
    assert pyxel.pget(*display.viewport.to_output(2,2))==color
    player.update(.25)
assert player.finished and player.index==2
player.restart()
assert player.index==0 and not player.finished
print('native sprite pixels passed')
"""
        env = os.environ.copy()
        env["SDL_AUDIODRIVER"] = "dummy"
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("native sprite pixels passed", result.stdout)
