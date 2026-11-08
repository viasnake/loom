"""Real Image.camera pixels, not a physical desktop/controller test."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeCameraTests(unittest.TestCase):
    def test_camera_snap_nested_restoration_and_hud_pixels(self):
        script = """
import pyxel
from loom import Camera2D, CameraView, DisplayConfig
from loom.display import PyxelDisplay
pyxel.init(80, 60, headless=True)
display = PyxelDisplay(pyxel, DisplayConfig(output_size=(80,60), world_size=(20,10)))
image = display.world
view = CameraView(image)
for offset in (-1.9,-1.5,-.5,-.1,0,.1,.5,1.5,1.9):
    camera = Camera2D((20,10), position=(offset,0))
    image.cls(0)
    image.camera(offset,0)
    image.pset(5,5,7)
    image.camera()
    native = [x for x in range(20) if image.pget(x,5)==7]
    assert native == [5-camera.origin[0]], (offset,native,camera.origin)
    image.cls(0)
    try:
        with view.apply(camera):
            image.pset(5,5,7)
            with view.apply(Camera2D((20,10), position=(0,0))):
                image.pset(0,0,3)
            image.pset(5,6,8)
            raise RuntimeError('restore')
    except RuntimeError:
        pass
    x,y = camera.world_to_view(5,5)
    assert image.pget(x,y)==7
    assert image.pget(x,6)==8
    assert camera.view_to_world(x,y)==(5,5)
    image.pset(1,1,10)
    assert image.pget(1,1)==10
    display.composite()
    output = display.viewport.to_output(x,y)
    assert pyxel.pget(*output)==7
    local = display.viewport.to_local(*output)
    assert camera.view_to_world(*local)==(5,5)
    pyxel.pset(0,0,11)
    assert pyxel.pget(0,0)==11
for origin in (2**24 - 20, -(2**24)):
    camera = Camera2D((20,10), position=(origin,0))
    image.cls(0)
    with view.apply(camera):
        image.pset(origin+5,5,7)
    assert image.pget(5,5)==7
    assert camera.view_to_world(5,5)==(origin+5,5)
print('native camera pixels passed')
"""
        env = os.environ.copy()
        env["SDL_AUDIODRIVER"] = "dummy"
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("native camera pixels passed", result.stdout)
