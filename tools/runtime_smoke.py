"""Exercise native GameApp callbacks and a queued resolution change."""

import pyxel
from loom import Scene
from loom.runtime import GameApp
from loom.display import DisplayConfig


class Probe(Scene):
    def __init__(self):
        self.frames = 0
        self.closed = False

    def update(self, frame, dt):
        self.frames += 1
        if self.frames == 2:
            app.request_display(DisplayConfig((640, 360), (320, 180)))
        if self.frames == 5:
            assert app.display.config.output_size == (640, 360)
            app.request_quit()

    def draw(self, display):
        display.world.cls(1)
        display.composite()

    def exit(self):
        self.closed = True
        assert self.frames == 5
        print("GameApp native callbacks, resize and cleanup passed", flush=True)


probe = Probe()
app = GameApp("Loom smoke", probe)
app.run(headless=True)
assert probe.closed and probe.frames == 5
print("GameApp native callbacks, resize and cleanup passed")
