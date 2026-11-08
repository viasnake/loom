Getting started
===============

Install from the repository with Python 3.11 or newer:

.. code-block:: console

   python -m pip install -e .
   python examples/showcase.py

The showcase includes an arcade screen, a turn-based/save screen and a Cube
screen. Tab/D-pad moves focus, Enter/A activates and Escape/B returns. The
arcade uses left/right to move and Enter to pause. Only Save writes progress.

A screen
--------

.. code-block:: python

   import pyxel
   from loom import DisplayConfig, GameApp, Scene

   class Play(Scene):
       def update(self, frame, dt):
           if "cancel" in frame.pressed:
               self.scenes.quit()

       def draw(self, display):
           display.world.cls(1)
           display.world.circ(160, 90, 20, 10)
           display.composite()
           pyxel.text(20, 20, "Escape to quit", 7)

   GameApp("My game", Play(), DisplayConfig((960, 540), (320, 180))).run()

The world renders at 320×180; text draws directly into the 960×540 output.
These are render pixels, not physical monitor pixels. ``frame.pointer`` uses
output coordinates; ``frame.world_pointer`` uses world coordinates or ``None``
in the surrounding margins. Do not apply OS DPI conversion a second time.

Use ``scenes.push()``, ``pop()`` and ``replace()`` for screen transitions.
Only the top screen receives input. Changes apply after update, not during
draw. Overlays can keep lower screens visible and pause their updates.
Call ``scenes.quit()`` rather than ``pyxel.quit()`` so exit hooks run first.

UI and resources
----------------

``Column`` holds ``Label`` and ``Button`` widgets and reuses its layout until
invalidated. Convert actions to ``UIInput`` and respect the returned
``UIResult`` before forwarding input to gameplay. The showcase demonstrates
this, including a pause overlay. Call ``Column.reset_input()`` when a screen
loses input ownership. It does not detect OS focus changes automatically.

``Palette`` assigns named colors to Pyxel's shared palette of up to 256 unique
RGB values. Apply it before loading images or GLB assets. Both render layers
share it; rebuild Cube shading after changing the palette.

``FontCatalog`` provides measurement, simple wrapping and bounded caching.
The layered text sample accepts a game-supplied font:

.. code-block:: console

   python examples/layers.py --font /path/to/font.ttf

Fonts are not bundled. Use a font whose license permits your intended use.
Text layout does not provide IME, shaping or Japanese kinsoku rules.

Saving
------

.. code-block:: python

   from loom import SaveStore

   store = SaveStore.for_app("com.example.game", version=1)
   store.save({"score": 10})
   state = store.load()

The game validates its own data. ``load()`` does not rewrite files; migrations
run in memory. Saving backs up the previous valid file before replacement.
Corrupt or future-version files block writes; recovery is explicit.

Saves are synchronous and single-writer. Avoid serializing large states in
frame updates. Use ``kind="settings"`` for device settings, separate from
progress intended for cloud synchronization. Atomic replacement is not a
universal guarantee against filesystem or power-loss failures.

Testing and packaging
---------------------

.. code-block:: console

   python -m unittest discover -s tests -v
   python tools/benchmark.py
   python tools/package_showcase.py

The tests assert lifecycle, input, persistence and display contracts. Native
regressions check pixel output and runtime resize/cleanup, not merely whether
the application starts. The benchmark is a measurement tool, not a pass/fail
test.

The packaging script builds ``dist/loom-showcase.pyxapp``. It still needs
Python and Pyxel. To create a runtime-containing distribution, use Pyxel's
``app2exe`` command on the target OS, then test it on a clean machine:

.. code-block:: console

   python -m pip install "pyxel[app2exe]==3.0.0"
   pyxel app2exe dist/loom-showcase.pyxapp

Loom does not upload builds or integrate Steamworks. Packaging is not evidence
of tested Windows, controller, Steam Cloud or Steam Deck support.
