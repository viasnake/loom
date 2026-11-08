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

``Column`` holds labels, buttons, toggles and sliders and reuses its layout until
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
``cancel``, ``next``, ``previous``, ``decrement`` and ``increment``. Change physical bindings in ``ActionMap``,
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
For UI over gameplay, use ``UIRouter`` below rather than hand-filtering each
frame. ``without()`` only removes named actions; it cannot track a gesture's
owner across frames or infer aliases of the same physical key.

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

Routing UI and game input
-------------------------

.. code-block:: python

   from loom import UIRouter

   router = UIRouter(
       [hud, inventory],  # back to front
       pointer_actions={"fire"},
   )
   result = router.update(frame)
   game.update(result.remaining)
   router.draw(canvas)

Only the frontmost hit panel receives a pointer gesture, and one active panel
receives navigation keys. Register aliases such as ``fire`` when they share
UI controls; built-in UI names are always included. These arguments add aliases
to logical action groups, not physical-key guesses.
``navigation_actions`` can similarly include game aliases of confirm/navigation.

A UI-owned action stays blocked through release, even outside the panel or
after its removal. Ordinary hover does not steal a release from a game-owned
action. A modal panel interrupts gameplay: held game actions receive one
cancellation release, and holding them through modal closure does not restart
them. Opening or closing a modal in a callback consumes that frame too.

Use ``router.update(frame, reset=True)`` on explicit focus loss together with
``ActionMap.reset()``. OS focus detection is not automatic. Pointer coordinates
remain observational data; coordinate-driven gameplay must respect
``result.pointer_consumed``. Wheel is routed per frame under the pointer,
separately from button capture.

``add()``, ``remove()`` and ``bring_to_front()`` manage top-level panels.

Settings controls
-----------------

.. code-block:: python

   from loom import Column, Slider, Toggle, UIRouter

   settings = Column([
       Toggle("Music", checked=True, on_change=set_music_enabled),
       Slider("Volume", value=0.6, minimum=0, maximum=1, step=0.1,
              on_change=set_volume),
   ], width=280)
   router = UIRouter([settings], navigation_actions={"left", "right"})

A toggle changes on pointer release inside the control or confirm. A slider
updates immediately when the control is pressed and follows the captured pointer,
clamping outside its range. Keyboard/D-pad decrement and increment change one
step per press; there is no implicit repeat. Default bindings use Left/Right
and D-pad Left/Right. Register game aliases of these keys with the router as
above so UI adjustment cannot also move the player.

Callbacks receive the new value only when it changes, including programmatic
assignment to ``checked`` or ``value``; construction does not call them. Reset,
cancel, scrolling, hiding or disabling a control ends an ongoing drag without
undoing changes already made. Persistence and audio effects remain game-owned;
these widgets do not write files or change global sound settings.

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

Rebinding and saved controls
----------------------------

``ActionMap.replace_bindings(mapping)`` replaces the complete map atomically.
``GameApp.request_bindings(mapping)`` validates and copies the same data, then
applies it after the current update. Before ``run()``, a request supplies the
initial bindings. An empty map disables named actions. Unknown or unavailable
backend key codes are not detected by Loom; choose codes for your target Pyxel
version and devices.

Changing bindings releases previously held logical actions once, marking them
in ``InputFrame.cancelled`` as well as ``released``. Cancellation ends an action
without committing it: ``UIRouter`` and ``UIInput.from_frame()`` reset capture
before handling it. Custom release-to-commit gameplay must check ``cancelled``
too. Keys already
down under the new map are ignored until released, so confirming a settings
choice does not also trigger gameplay. Replacing with identical bindings does
not interrupt input. ``reset()`` does not bypass a pending rebind's suppression.
Call the router with ``reset=True`` when switching input context as well.

.. code-block:: python

   controls = SaveStore.for_app("com.example.game", version=1, kind="settings")
   controls.save({"bindings": app.actions.to_data()})
   saved = controls.load()
   app.request_bindings(saved["bindings"])

For initial startup, catch ``FileNotFoundError`` and retain the defaults.
``to_data()`` returns an independent JSON-compatible mapping of action names to
key-code lists. Validate the application's settings envelope before indexing it;
invalid bindings raise without changing the current or pending map. Saving is
explicit, not a side effect of each key change. A game should retain a recovery
route if the player removes all menu controls. There is no cross-backend key translation.

Editing controls
----------------

``BindingEditor`` keeps a draft separate from live controls. Defaults define the
known action names; supplied current bindings must contain those same names.
``conflicts(action, keys)`` previews other actions sharing the proposed keys.
``assign()`` rejects conflicts by default. Choose ``conflict="share"`` to retain
shared keys or ``conflict="reassign"`` to remove those keys from other actions.
``clear(action)`` leaves an unbound action; ``restore_defaults()`` discards the
draft edits. Apply with ``app.request_bindings(editor.bindings)`` and save only
when the user confirms. Reassigning can leave another action unbound: the game
owns required menu controls and recovery policy.

``KeyCapture`` tracks a capture session, not a window or polling loop. Call
``begin(action, app.actions.physical_held)`` when opening the prompt, then feed
``update(app.actions.physical_held)`` once per scene update. Opening keys are
ignored until released. Simultaneous new keys produce ``ambiguous`` instead of
an arbitrary choice; release and retry. ``cancel()`` ends capture explicitly.
The game decides which key means cancel and presents conflicts before applying.

Pass a finite set of acceptable backend key codes as ``GameApp(watched_keys=...)``.
``ActionMap`` polls the union of bound and watched keys once per sample, exposing
immutable ``physical_held`` and ``physical_pressed`` snapshots. Raw state is
available even while named actions are suppressed by rebinding. It is intended
for capture, not gameplay: it bypasses UI routing. Keep gameplay paused or modal
while capturing. These primitives do not scan every possible key code, infer
key labels, support chords or display a built-in capture dialog.

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
