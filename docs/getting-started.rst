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
invalidated. Use ``UIInput.from_frame(frame)`` and respect the returned
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

To use the same font for UI measurement and rendering:

.. code-block:: python

   from loom import Button, Column, FontCatalog, Label
   from loom.ui import Typography

   fonts = FontCatalog()
   fonts.register("body", pyxel.Font("assets/body.ttf", 18), line_height=24)
   panel = Column(
       [Label("Settings\nChoose an option"), Button("Continue", continue_game)],
       width=360,
       typography=Typography(fonts, font="body"),
   )

Default widget heights grow to fit the measured line boxes. Changing text or
re-registering a font invalidates the layout before hit testing. An explicit
``height`` overrides automatic sizing. Text does not wrap automatically. Unbounded panels do not clip; provide
sufficient width and height, or use the finite viewport described below. The same typography is used
by ``panel.draw(pyxel)``, so no custom drawing adapter is needed. Buttons center
text vertically. Custom canvases used with typography must accept the ``font``
keyword in ``text()``, as Pyxel and Pyxel Image do; see ``FontCanvas``.

``UIInput.from_frame()`` uses the standard action names ``primary``, ``confirm``,
``cancel``, ``next`` and ``previous``. Change physical bindings in ``ActionMap``,
not in the UI. It converts edge events, so holding a button does not repeatedly
activate it.

Fonts are not bundled. Use a font whose license permits your intended use.
Text layout does not provide IME, shaping or Japanese kinsoku rules.

Scrollable panels
-----------------

.. code-block:: python

   from loom import Button, Column, PyxelCanvas, UIInput

   canvas = PyxelCanvas(pyxel)
   panel = Column(buttons, width=240, viewport_height=240)
   result = panel.update(UIInput.from_frame(frame))
   panel.draw(canvas)

``viewport_height`` is the panel's outer height, including padding. Content is
clipped to the inner area; clipped parts cannot be clicked. ``scroll_offset``
is an integer pixel offset clamped to the content. Tab, D-pad focus navigation
and confirm reveal the focused item. Idle updates do not undo manual scrolling.
Items taller than the viewport align to its top.

``InputFrame.wheel`` is the backend delta, positive upward.
``UIInput.from_frame(frame, scroll_step=24)`` converts it to UI pixels. Wheel
input is handled only over the panel and is consumed there even at its ends.
When ``result.pointer_consumed`` is true, do not also feed the pointer gesture
or wheel to the game. With the standard action names, for example:

.. code-block:: python

   from dataclasses import replace

   if result.pointer_consumed:
       frame = replace(frame.without({"primary"}), wheel=0)

``without()`` removes named actions, not wheel data. A modal screen can instead
withhold the whole frame from gameplay.

Scrolling cancels click activation but retains ownership of an ongoing pointer
gesture until release, preventing a click on content newly moved underneath it.

Finite panels require a canvas with scoped clipping. ``PyxelCanvas`` supports
both Pyxel and Image targets. Use ``canvas.clipped(Rect(...))`` for an outer
clip: nested clips intersect and restore on exceptions. Pyxel has no getter
for existing clip state, so do not mix direct ``pyxel.clip()`` calls with the
adapter. Layout/input bounds remain the panel's viewport; an outer drawing clip
does not change its hit area. Keep interactive panels within that outer area.

Run ``python examples/scroll.py`` for a 30-item stage list. This is vertical
scrolling, not nested UI, horizontal scrolling or large-list virtualization.

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
