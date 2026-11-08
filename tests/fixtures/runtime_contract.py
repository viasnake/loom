"""Report actual native callback observations to the parent unittest process."""

import json
import pyxel
from loom import DisplayConfig, GameApp, Scene


class ResizeAndQuit(Scene):
    def __init__(self):
        self.report = {"update_sizes": [], "exit_count": 0}

    def update(self, frame, dt):
        self.report["update_sizes"].append([pyxel.width, pyxel.height])
        if len(self.report["update_sizes"]) == 1:
            self.report["before_request"] = [pyxel.width, pyxel.height]
            app.request_display(DisplayConfig((42, 30), (7, 5)))
            self.report["after_request"] = [pyxel.width, pyxel.height]
        else:
            self.scenes.quit()

    def draw(self, display):
        display.world.cls(2)
        display.composite()
        self.report["draw_size"] = [pyxel.width, pyxel.height]
        self.report["draw_pixels"] = [pyxel.pget(0, 0), pyxel.pget(41, 29)]

    def exit(self):
        self.report["exit_count"] += 1
        print("CONTRACT:" + json.dumps(self.report), flush=True)


app = GameApp("Runtime contract", ResizeAndQuit(), DisplayConfig((24, 18), (8, 6)))
app.run(headless=True)
