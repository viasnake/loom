# Loom

A small, code-first game framework on **Pyxel 3.0 / Python 3.11+**.
Loom owns application screens, UI input, render surfaces and persistence. Your
game owns its rules. Pyxel/Cube still owns drawing and 3D physics.

This is an **early alpha**, not a complete engine or a Steam-certified runtime.
No PRISM code or gameplay concepts are required.

## Try it

```sh
python -m pip install -e .
python examples/showcase.py
python examples/layers.py --font /path/to/a/legally-usable-japanese-font.ttf
```

The showcase has an arcade screen, a turn-based/save screen and a Cube screen.
Tab / D-pad moves focus, Enter / A activates, Escape / B returns. Mouse buttons
activate on release inside the button that owned the press. The arcade uses
left/right and Enter pauses it. Only the explicit Save button writes progress.
Fonts are not bundled; the layers sample defaults to the built-in Latin font.

## Small public primitives

```python
from loom import Scene
from loom.runtime import GameApp
from loom.display import DisplayConfig

class Play(Scene):
    def update(self, frame, dt):
        # frame.pointer: UI/screen pixels; world_pointer: scaled world or None.
        if "cancel" in frame.pressed:
            self.scenes.quit()

    def draw(self, display):
        display.world.cls(1)       # 320 x 180 world, reused Image
        display.composite()       # integer-scale to the output
        # Draw sharp UI directly through Pyxel here.

GameApp("My game", Play(), DisplayConfig((960, 540), (320, 180))).run()
```

- `SceneStack`: deferred push/pop/replace; top scene alone owns input. A modal
  can freeze lower updates while letting them draw. Call `scenes.quit()` rather
  than `pyxel.quit()` so exit hooks run before Pyxel terminates the process.
- `ActionMap`: named actions, held/pressed/released snapshots and explicit reset.
- `Column`, `Label`, `Button`: retained UI, cached layout, focus, pointer capture
  and modal input consumption. `UIResult` tells a scene what it must not pass
  through to the game. See `examples/showcase.py` for frame conversion.
- `DisplayConfig`, `Viewport`, `PyxelDisplay`: one world buffer and high-resolution
  screen; fit/integer scaling and margin-aware coordinates. Sizes are **render
  pixels**, not physical OS window pixels. Pyxel already converts mouse coords.
- `Palette`: names resolved once to a shared palette of up to 256 unique RGB
  colors. Apply before loading assets; do not let individual assets replace it.
  Rebuild any Cube shading table after a palette change.
- `FontCatalog`: game-supplied fonts, measurement, simple wrapping and bounded
  caching. It is not a shaping/IME/Japanese kinsoku engine.
- `SaveStore`: versioned JSON, backup-before-replace, explicit migration/recovery,
  future-version protection. `AppPaths` separates progress and device settings.

## Storage

```python
from loom.storage import SaveStore
store = SaveStore.for_app("com.example.game", version=1)
store.save({"score": 10})
state = store.load()
```

The game must validate its own data. Saves are synchronous: do not serialize
large states during frame updates. One process owns each store. `load()` does
not rewrite old saves; migrations run in memory, and the previous valid file is
backed up on save. Corrupt/future versions block writes. Call `recover()`
explicitly for a valid backup. There is no multi-writer or universal power-loss
guarantee. Keep settings/caches out of cloud-synced progress.

## Verification

```sh
python -m unittest discover -s tests -v
python tools/smoke.py
python tools/runtime_smoke.py
python tools/benchmark.py
```

Pure tests need no display or Pyxel import. Native smoke uses real Pyxel buffers
in **headless** mode, not a physical window, and temporary save locations.
`python tools/smoke.py artifacts` also captures actual output PNGs.
Measurements and limitations: [docs/validation.md](docs/validation.md).
Architecture and next steps: [docs/design.md](docs/design.md).

## Deliberately not implemented yet

Nested/scrolling UI, text clipping, runtime key rebinding UI, automatic OS focus
notifications, audio buses, asynchronous saves, an asset pipeline, Steamworks
bindings, a general ECS or editor. Do not mistake the alpha for these features.
`ActionMap.reset()` and `Column.reset_input()` provide hooks but do not detect
Alt-Tab themselves. Built-in button text is not automatically clipped.

## Desktop / Steam path

Pyxel's official `package` and `app2exe` commands can produce a runtime-containing
application. `tools/package_showcase.py` builds a self-contained source tree and
`.pyxapp`; run `pyxel app2exe dist/loom-showcase.pyxapp` **on the target OS**.
This repository does not publish to Steam, provision accounts, or upload builds.
Windows executable launch, DPI, physical gamepads, long-session memory behavior,
Steam Cloud and Steam Deck remain explicit acceptance work, not established
support. See [docs/design.md](docs/design.md).
