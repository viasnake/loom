"""Low-resolution world + sharp text. Optional: python layers.py --font PATH.

Supply a legally usable font containing the desired glyphs for Japanese text.
No system-specific font is silently packaged into your game.
"""

import argparse
import pyxel
from loom.app import Scene
from loom.runtime import GameApp
from loom.text import FontCatalog


class Layers(Scene):
    def __init__(self, font_path=None):
        self.path = font_path
        self.angle = 0

    def enter(self, scenes):
        super().enter(scenes)
        self.fonts = FontCatalog()
        if self.path:
            self.fonts.register("body", pyxel.Font(self.path, 18), line_height=24)

    def update(self, frame, dt):
        self.angle += dt * 40
        if "cancel" in frame.pressed:
            self.scenes.quit()

    def draw(self, display):
        image = display.world
        image.cls(1)
        for i in range(15):
            image.circ(
                15 + i * 21, 90 + pyxel.sin(self.angle + i * 20) * 30, 8, 3 + i % 12
            )
        display.composite()
        if self.path:
            self.fonts.draw(
                pyxel, 32, 32, "低解像度の世界と、高解像度の文字。", 7, "body"
            )
        else:
            self.fonts.draw(
                pyxel,
                32,
                32,
                "320 x 180 world / 960 x 540 UI. Supply --font for larger Japanese text.",
                7,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--font")
    args = parser.parse_args()
    GameApp("Loom layers", Layers(args.font)).run()
