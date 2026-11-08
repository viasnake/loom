"""Finite standalone distribution probe, not a game example."""

import json
import os
from pathlib import Path
import sys

import loom
import pyxel
from loom import AssetStore, GameApp, SaveStore, Scene

output = Path(os.environ["LOOM_PROBE_OUTPUT"])
saves = SaveStore(Path(os.environ["LOOM_PROBE_SAVES"]))
assets = AssetStore(Path(__file__).resolve().parent / "assets")
events = []


class Finish(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        events.append("finish.enter")
        self.rendered_pixel = None

    def draw(self, target):
        target.world.cls(pixel)
        target.composite()
        self.rendered_pixel = pyxel.pget(target.viewport.x, target.viewport.y)

    def update(self, frame, dt):
        if self.rendered_pixel is None:
            return
        try:
            previous = saves.load()["runs"]
        except FileNotFoundError:
            previous = 0
        saves.save({"runs": previous + 1})
        events.append("finish.update")
        self.scenes.quit()

    def exit(self):
        events.append("finish.exit")
        output.write_text(
            json.dumps(
                {
                    "frozen": bool(getattr(sys, "frozen", False)),
                    "executable": sys.executable,
                    "loom_origin": loom.__file__,
                    "game_origin": __file__,
                    "asset_origin": str(assets.path("pixel.png")),
                    "pyxel_origin": pyxel.__file__,
                    "bundle_root": getattr(sys, "_MEIPASS", None),
                    "pixel": pixel,
                    "rendered_pixel": self.rendered_pixel,
                    "runs": saves.load()["runs"],
                    "events": events,
                    "python": sys.version,
                }
            ),
            encoding="utf-8",
        )
        assets.close()


class Start(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        global pixel
        image = pyxel.Image(1, 1)
        image.load(0, 0, str(assets.path("pixel.png")))
        pixel = image.pget(0, 0)
        events.append("start.enter")

    def update(self, frame, dt):
        events.append("start.update")
        self.scenes.replace(Finish())

    def exit(self):
        events.append("start.exit")


GameApp("Loom distribution contract", Start()).run(headless=True)
