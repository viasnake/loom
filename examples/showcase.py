"""Run: python examples/showcase.py (after pip install -e .)."""

import pyxel
from loom.app import Scene
from loom.runtime import GameApp
from loom.ui import Button, Column, Label, UIInput
from loom.palette import Palette
from loom.storage import SaveStore, AppPaths, SaveError


class Menu(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        # A single shared palette, not a separate palette per layer.
        Palette(
            {
                "background": 0x121824,
                "panel": 0x202B3D,
                "shadow": 0x344153,
                "ink": 0x526A75,
                "blue": 0x46698A,
                "button": 0x405A71,
                "muted": 0x95A9B0,
                "text": 0xE5EAD5,
                "red": 0xDE6563,
                "gold": 0xE6B566,
                "focus": 0xFFD982,
                "leaf": 0x7AAB80,
                "active": 0x529EAF,
                "hover": 0x6A7D93,
                "purple": 0x9282BA,
                "white": 0xFFFFFF,
            }
        ).apply(pyxel)
        self.ui = Column(
            [
                Label("LOOM / PYXEL 3"),
                Label("One world surface. A sharper UI layer."),
                Button("Arcade + pause", lambda: scenes.push(Arcade())),
                Button("Turn-based + save", lambda: scenes.push(Turns())),
                Button("Cube / low-resolution 3D", lambda: scenes.push(CubeRoom())),
                Button("Quit", scenes.quit),
            ],
            x=300,
            y=160,
            width=360,
            padding=12,
            gap=8,
        )

    def update(self, frame, dt):
        self.ui.update(UIInput.from_frame(frame))

    def draw(self, display):
        display.world.cls(0)
        for i in range(12):
            display.world.rect(8 + i * 27, 40 + (i % 3) * 14, 20, 60, 2 + i % 4)
        display.composite()
        self.ui.draw(pyxel)

    def pause(self):
        self.ui.reset_input()

    def resume(self):
        self.ui.reset_input()


class Pause(Scene):
    opaque = False

    def enter(self, scenes):
        super().enter(scenes)
        self.ui = Column(
            [Label("PAUSED"), Button("Resume", scenes.pop)],
            x=360,
            y=220,
            width=240,
            modal=True,
            on_cancel=scenes.pop,
        )

    def update(self, frame, dt):
        self.ui.update(UIInput.from_frame(frame))

    def draw(self, display):
        self.ui.draw(pyxel)


class Arcade(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        self.x = 150.0
        self.y = 25.0
        self.velocity = 35.0
        self.score = 0

    def update(self, frame, dt):
        if "cancel" in frame.pressed:
            self.scenes.pop()
            return
        if "confirm" in frame.pressed:
            self.scenes.push(Pause())
            return
        self.x = max(
            5,
            min(
                285,
                self.x + (("right" in frame.held) - ("left" in frame.held)) * 130 * dt,
            ),
        )
        self.y += self.velocity * dt
        if self.y > 145:
            self.score += int(abs((self.y * 7) % 300 - self.x) < 25)
            self.y = 12

    def draw(self, display):
        world = display.world
        world.cls(0)
        world.line(0, 166, 319, 166, 5)
        world.rect(self.x, 150, 30, 5, 10)
        world.circ((self.y * 7) % 300, self.y, 4, 12)
        display.composite()
        pyxel.text(20, 20, "ARCADE: arrows / A-D move | Enter pause | Esc menu", 7)
        pyxel.text(20, 34, f"Catches: {self.score}", 10)


class Turns(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        self.turn = 0
        self.message = "No save yet."
        self.store = SaveStore(AppPaths.for_app("loom.showcase").progress)
        self.ui = Column(
            [
                Label("TURN-BASED SAMPLE"),
                Button("Take a turn", self.advance),
                Button("Save", self.save),
                Button("Load", self.load),
                Button("Back", scenes.pop),
            ],
            x=610,
            y=150,
            width=300,
        )

    def advance(self):
        self.turn += 1

    def save(self):
        try:
            self.store.save({"turn": self.turn})
            self.message = "Saved."
        except (SaveError, OSError) as e:
            self.message = type(e).__name__

    def load(self):
        try:
            data = self.store.load()
            if type(data.get("turn")) is not int or data["turn"] < 0:
                raise ValueError("Invalid turn")
            self.turn = data["turn"]
            self.message = "Loaded."
        except (SaveError, OSError, ValueError) as e:
            self.message = type(e).__name__

    def update(self, frame, dt):
        result = self.ui.update(UIInput.from_frame(frame))
        if not result.keyboard_consumed and "cancel" in frame.pressed:
            self.scenes.pop()

    def draw(self, display):
        w = display.world
        w.cls(0)
        for y in range(4):
            for x in range(4):
                w.rect(12 + x * 36, 25 + y * 30, 32, 26, 3 + (x + y) % 3)
        w.circ(28 + (self.turn % 4) * 36, 38 + ((self.turn // 4) % 4) * 30, 8, 10)
        display.composite()
        self.ui.draw(pyxel)
        pyxel.text(630, 320, f"Turn {self.turn} | {self.message}", 7)


class CubeRoom(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        from pyxel.cube import Node, Camera, Mat4, Vec3

        class Box(Node):
            def on_draw(self):
                self.box(Mat4.IDENTITY, Vec3(1.5, 1.5, 1.5), 12)

        self.node = Node()
        self.box = Box()
        self.node.add_child(self.box)
        self.node.camera = Camera()
        self.node.camera.transform = Mat4.look_at(Vec3(4, 3, -6), Vec3(0, 0, 0))
        self.node.camera.clear_color = 0
        self.angle = 0

    def update(self, frame, dt):
        from pyxel.cube import Mat4, Vec3

        if "cancel" in frame.pressed:
            self.scenes.pop()
            return
        self.angle += dt * 25
        self.box.transform = Mat4.from_euler(Vec3(0, self.angle, 0))

    def draw(self, display):
        self.node.draw(0, 0, *display.config.world_size, target=display.world)
        display.composite()
        pyxel.text(20, 20, "CUBE: 320 x 180 world / 960 x 540 UI | Esc menu", 7)

    def exit(self):
        self.node.destroy()


if __name__ == "__main__":
    GameApp("Loom showcase", Menu()).run()
