"""Low-resolution world with font-aware UI: python layers.py --font PATH.

Supply a legally usable font containing the desired glyphs for Japanese text.
No system-specific font is silently packaged into your game.
"""

import argparse
import pyxel
from loom import Button, Column, FontCatalog, GameApp, Label, Scene, UIInput
from loom.ui import Typography


class Layers(Scene):
    def __init__(self, font_path=None):
        self.path = font_path
        self.angle = 0
        self.paused = False

    def enter(self, scenes):
        super().enter(scenes)
        fonts = FontCatalog()
        font = "default"
        if self.path:
            fonts.register("body", pyxel.Font(self.path, 18), line_height=24)
            font = "body"
        title = (
            "低解像度の世界と\n高解像度のインターフェース"
            if self.path
            else "LOW-RES WORLD / SHARP UI\nSupply --font for larger Japanese text."
        )
        self.toggle = Button("一時停止" if self.path else "Pause", self.toggle_pause)
        self.panel = Column(
            [
                Label(title),
                self.toggle,
                Button("終了" if self.path else "Quit", scenes.quit),
            ],
            x=32,
            y=32,
            width=420,
            padding=16,
            gap=12,
            typography=Typography(fonts, font=font),
        )

    def toggle_pause(self):
        self.paused = not self.paused
        if self.path:
            self.toggle.text = "再開" if self.paused else "一時停止"
        else:
            self.toggle.text = "Resume" if self.paused else "Pause"

    def update(self, frame, dt):
        result = self.panel.update(UIInput.from_frame(frame))
        if not result.keyboard_consumed and "cancel" in frame.pressed:
            self.scenes.quit()
        if not self.paused:
            self.angle += dt * 40

    def draw(self, display):
        image = display.world
        image.cls(1)
        for i in range(15):
            image.circ(
                15 + i * 21, 90 + pyxel.sin(self.angle + i * 20) * 30, 8, 3 + i % 12
            )
        display.composite()
        self.panel.draw(pyxel)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--font")
    args = parser.parse_args()
    GameApp("Loom layers", Layers(args.font)).run()
