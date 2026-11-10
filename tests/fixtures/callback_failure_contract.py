"""Observe cleanup before native Pyxel handles a failing Python callback."""

import json
import sys

from loom import DisplayConfig, GameApp, Scene

hook, cleanup_mode = sys.argv[1:]
events = []


class Overlay(Scene):
    def update(self, frame, dt):
        if hook == "quit":
            self.scenes.quit()
        if hook == "update":
            raise ValueError("gameplay failure marker")

    def draw(self, display):
        if hook == "draw":
            raise ValueError("render failure marker")

    def exit(self):
        events.append("overlay exit")
        self.scenes.close()  # Reentrant cleanup must not repeat any exit hook.
        if cleanup_mode == "fail":
            raise OSError("cleanup failure marker")


class Root(Scene):
    def update(self, frame, dt):
        self.scenes.push(Overlay())

    def exit(self):
        events.append("root exit")
        print("CLEANUP:" + json.dumps(events), flush=True)


GameApp("Callback failure contract", Root(), DisplayConfig((32, 32), (16, 16))).run(
    headless=True
)
