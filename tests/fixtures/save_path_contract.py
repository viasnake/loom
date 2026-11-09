"""Keep an explicitly relative save root stable across native initialization."""

import json
from pathlib import Path

from loom import GameApp, SaveStore, Scene

launch = Path.cwd()
store = SaveStore("progress")
store.save({"score": 1})


class Resume(Scene):
    def update(self, frame, dt):
        state = store.load()
        state["score"] += 1
        store.save(state)
        print(
            "SAVES:"
            + json.dumps({"cwd_changed": Path.cwd() != launch, "state": store.load()}),
            flush=True,
        )
        self.scenes.quit()


GameApp("Relative save contract", Resume()).run(headless=True)
