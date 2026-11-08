"""A bounded stage list with wheel and keyboard/gamepad navigation."""

import pyxel
from loom import Button, Column, GameApp, PyxelCanvas, Scene, UIInput


class StageList(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        self.selected = None
        self.canvas = PyxelCanvas(pyxel)
        self.panel = Column(
            [
                Button(f"Stage {stage:02}", lambda stage=stage: self.select(stage))
                for stage in range(1, 31)
            ],
            x=40,
            y=60,
            width=240,
            viewport_height=240,
            padding=8,
        )

    def select(self, stage):
        self.selected = stage

    def update(self, frame, dt):
        result = self.panel.update(UIInput.from_frame(frame))
        if not result.keyboard_consumed and "cancel" in frame.pressed:
            self.scenes.quit()

    def draw(self, display):
        pyxel.cls(0)
        pyxel.text(40, 32, "STAGES / WHEEL OR TAB / DPAD", 7)
        self.panel.draw(self.canvas)
        if self.selected is not None:
            pyxel.text(320, 80, f"Selected stage {self.selected:02}", 10)


if __name__ == "__main__":
    GameApp("Loom scrolling", StageList()).run()
