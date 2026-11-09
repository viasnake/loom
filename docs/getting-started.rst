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
output coordinates; ``frame.world_pointer`` identifies the rendered source pixel
in the world surface, or ``None`` in margins. It is discrete in both fit and
integer scaling; use ``Viewport.to_local`` for continuous geometry. Do not apply
OS DPI conversion a second time.

Use ``scenes.push()``, ``pop()`` and ``replace()`` for screen transitions.
Only the top screen receives input. Changes apply after update, not during
draw. Overlays can keep lower screens visible and pause their updates.
Call ``scenes.quit()`` rather than ``pyxel.quit()`` so exit hooks run first.
SceneStack initialization interruptions clean the partial scene; ``close()``
attempts every exit once even on KeyboardInterrupt/SystemExit, then raises grouped
cleanup failures.

UI and resources
----------------

``Column`` holds labels, buttons, toggles, sliders and progress bars and reuses its layout until
invalidated. Use ``UIInput.from_frame(frame)`` and respect the returned
``UIResult`` before forwarding input to gameplay. The showcase demonstrates
this, including a pause overlay. Call ``Column.reset_input()`` when a screen
loses input ownership. It does not detect OS focus changes automatically.

``ProgressBar(0.75, color=11)`` displays a fraction without text or input handling.
Set ``bar.value = health / max_health`` or a cooldown fraction; finite values
clamp to 0..1. Value changes redraw without relayout. The game owns units,
zero-maximum handling and animation; use ``Timeline`` for an animated value.
The bar is skipped by keyboard navigation, while its panel retains normal
pointer ownership. No automatic timer, percentage label or background job is added.

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
``height`` overrides automatic sizing. Text does not wrap unless requested with
``Label(..., wrap=True)``. Unbounded panels do not clip; provide
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

Wrapped descriptions and dialogue
---------------------------------

Use ``Label(wrap=True)`` for plain paragraphs constrained to the panel width:

.. code-block:: python

   description = Label("Find the old tower beyond the river, then return here.", wrap=True)
   panel = Column([description, Button("Continue", continue_game)], width=240)
   panel.configure(width=160)  # Reflows before the next update or draw.
   description.text = "The tower door is open."

Wrapping uses ``Column.width - 2 * padding`` and the panel's typography. Without
``Typography`` it uses the built-in 4-pixel advance and 6-pixel line box; no
font-aware canvas is required. Automatic height grows with the wrapped lines.
Changing text, ``wrap``, panel width/padding or font registration invalidates the
layout. Idle updates and draws reuse the measured lines, including in scrollable
panels. Custom widgets can override ``measure_height(width, typography)`` for
width-aware sizing; its default delegates to the existing ``layout_height`` hook.

This is plain-text wrapping, not a rich-text engine. Explicit newlines and empty
lines are preserved; other whitespace is collapsed. Long words and Japanese text
split at code points, not grapheme clusters or Japanese kinsoku boundaries. Use a
font with the required glyphs. A single glyph wider than the available width still
overflows; explicit widget heights can also overflow. A finite panel clips to its
viewport, not to individual label boxes. The built-in fixed-width font wraps in
linear work. Custom fonts use a temporary measurement cache bounded by
``FontCatalog.max_entries``; only the final wrapped result enters the shared
cache, so intermediate prefixes do not evict other measurements. This avoids
retaining prefixes after wrapping, not their temporary peak memory. Custom font
widths need not be additive or monotonic, so long unbroken tokens can still
require quadratic measurement work. Split very large custom-font documents into
smaller paragraphs/pages ahead of time. Other widgets, and labels with
``wrap=False`` (the default), retain their previous unwrapped behavior.

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

For application-directed input interruption, use ``app.request_input_cancel()``
(or ``ActionMap.cancel()`` when sampling manually). OS focus detection is not
automatic. The cancellation frame resets the router's captured gestures. Pointer coordinates
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

Time and animation
------------------

.. code-block:: python

   from loom import Timeline
   from loom.timing import ease_out_cubic

   animation = Timeline()
   panel_x = animation.tween(-240, 20, 0.35, ease=ease_out_cubic)
   animation.call_later(1.0, show_hint)

   # In the owning scene's update:
   animation.update(dt)
   # In draw, read panel_x.value and round at the pixel boundary.
   # In exit:
   animation.clear()

Time advances only through ``update(dt)``. A scene that is paused by an overlay
naturally pauses its timeline; Loom does not register global animation tasks.
Clear scene-owned timelines on exit to discard outstanding notifications and
captured callback references. Timers are one-shot, not repeating or wall-clock
jobs. Delays can be zero (run on the next update); tween durations must be
positive. Large ``dt`` completes a task once and lands a tween exactly at its
endpoint, without repeated catch-up callbacks. Time uses floating-point seconds;
roundoff in repeated updates can postpone a boundary to the following update.
This is not an exact integer-tick scheduler.

Handles expose ``done``, ``cancelled`` and ``cancel()``; tweens expose ``value``.
Cancelling does not run completion callbacks. Tasks scheduled inside callbacks
start on the next update, not in unused time from the current one. Recursive
updates are rejected. Callback or easing exceptions cancel the remaining tasks
and propagate; there is no rollback of callbacks already run. The timeline can
then be reused. Easing receives normalized progress and returns a finite value;
overshoot is allowed, but non-finite interpolation is rejected. Extremely large
endpoints combined with overshoot can overflow intermediate float operations;
keep animation values within a practical numeric range.

This is numeric interpolation, not an alpha compositor, property-binding system,
async scheduler or animation editor. Games decide how values affect drawing.

Audio channels
--------------

.. code-block:: python

   from loom import AudioMixer

   # Construct after pyxel.init, while these channels are idle.
   audio = AudioMixer(channels=pyxel.channels,
                      buses={"music": (0,), "effects": (1, 2)})
   audio.master_volume = 0.8
   audio.set_bus_volume("effects", 0.5)
   voice = audio.play("effects", sound_id)
   # voice is None when all channels in that bus are occupied.
   audio.close()  # e.g. in the owning scene/application cleanup

A bus reserves a disjoint set of channels. Playback uses an idle channel and
never steals an existing voice. The mixer owns those channels exclusively;
do not use direct channel playback or another mixer on them while it is open.
Other channels are untouched. Sound/music assets remain game-owned; the mixer
does not rewrite their volume data or call Pyxel's global stop.

Gain is the original channel gain multiplied by master and bus volumes (0..1).
This preserves Pyxel's default headroom rather than replacing its base gain
with 1. Muting sets gain to zero without stopping playback. ``Voice.active``
checks current playback, and a stale ``Voice.stop()`` cannot stop a newer voice
that reused its channel. ``stop(bus)`` stops one group; ``stop()`` stops all owned
channels. ``close()`` stops owned playback and restores its original gains,
attempting every channel even when a backend operation fails. Cleanup failures
are grouped and reported; the mixer remains closed and a second ``close()`` does
not retry them. Recover failed backend operations explicitly. Gain-setting errors
attempt rollback; if rollback also fails, handle the reported failures before
continuing playback.

Call ``close()`` explicitly at the owner's lifetime boundary. A paused scene does
not automatically pause sound, and there is no streaming, crossfade, priority
stealing, ducking or automatic global mixer. Native tests verify gain and channel
state with a dummy audio driver; they do not certify audible quality or latency.

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

Two-dimensional gamepad sticks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Register analog axes separately from digital keys. Pyxel's ``btn`` does not
accept analog axis codes; they must be read through ``btnv``:

.. code-block:: python

   from loom import GameApp, StickBinding

   app = GameApp(
       "Explorer", initial_scene,
       sticks={"move": StickBinding(
           pyxel.GAMEPAD1_AXIS_LEFTX, pyxel.GAMEPAD1_AXIS_LEFTY,
           deadzone=0.2, invert_y=False,
       )},
   )
   # In Scene.update(frame, dt), AFTER routing through any UI:
   routed = router.update(frame).remaining
   dx, dy = routed.sticks.get("move", (0.0, 0.0))

For manual sampling, pass ``sticks=...`` to ``ActionMap`` and call
``actions.sample(pyxel.btn, axis_value=pyxel.btnv)``. Shared analog codes are
polled once per sample, separately from digital/watched keys. Stick names cannot
collide with digital action names, and registered axis codes cannot occur in
digital bindings or ``watched_keys``. Rebinding validates these constraints too.
Stick configuration is fixed at construction; ``ActionMap.to_data()`` and
``BindingEditor`` cover digital bindings only. Stick persistence and runtime
stick reassignment are not part of these APIs.

Pyxel 3's native SDL path supplies signed 16-bit axis values (-32768..32767).
Loom clamps raw values, normalizes each sign separately, applies a radial
``deadzone`` (0 inclusive to 1 exclusive), rescales the remaining travel and
limits diagonal magnitude to one. ``invert_x``/``invert_y`` reverse components.
A neutral stick is ``(0.0, 0.0)``. ``InputFrame.sticks`` is an independent readonly
snapshot; ``without(names)`` removes corresponding stick names too.

Stick movement does not create digital ``held``, ``pressed`` or ``released``
actions. On interruption, a previously nonneutral stick's name appears once in
``cancelled`` only. ``ActionMap.cancel()`` and changed digital bindings suppress
sticks until **both** components return inside the radial deadzone. ``reset()``
alone retains values and never bypasses existing suppression. Modal panels and
``UIRouter.update(..., reset=True)`` similarly output zero vectors and keep them
blocked after closing until neutral. Normal nonmodal hover does not stop movement;
explicit pointer/navigation aliases can opt a named stick into consumption.
Always use the router's remaining frame for gameplay, not an independently polled
axis or an earlier frame that bypasses the modal.

The range contract comes from the `Pyxel 3 SDL event adapter
<https://github.com/kitao/pyxel/blob/v3.0.0/crates/pyxel-core/src/platform/sdl2/poll_events.rs>`_.
Headless ``set_btnv`` can supply out-of-range integers, hence the clamp. Synthetic
axis and native adapter tests do not verify a physical controller or Steam Deck.
Device connection/disconnection detection, OS focus detection, trigger axes,
analog UI navigation and runtime stick rebinding are not provided here.

Explicit input interruption
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``app.request_input_cancel()`` queues interruption before the next frame's physical
sample. Requests made during a scene update leave the current immutable frame
unchanged; requests made before ``run()`` suppress keys held at startup. Repeated
requests before the next sample coalesce. For a manually driven input map, call
``actions.cancel()`` before its next ``sample()``.

Previously held digital actions are reported once in both ``released`` and
``cancelled``; interrupted nonneutral sticks appear in ``cancelled`` only. Stop their gameplay effects, but do not commit release-triggered
attacks or clicks when the action is also cancelled. Keys down at the interruption
sample stay suppressed until released and pressed again. ``UIRouter`` and
``UIInput.from_frame`` already handle cancellation without committing Button or
Slider gestures. The interruption sample also discards wheel movement and raw
``physical_pressed`` edges. Pointer coordinates and ``physical_held`` remain raw;
call ``KeyCapture.cancel()`` separately if a binding capture is active.

``reset()`` retains its narrower resynchronization behavior: it suppresses edges,
but does not cancel held input. Cancellation can be combined with reset or a
binding replacement without losing its pending notification. No OS focus detector
is provided: Pyxel 3 exposes no supported focus event API here, so the application
must request interruption at its own pause, screen or settings boundaries.

Binding replacement
~~~~~~~~~~~~~~~~~~~

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

Resource paths
--------------

Pyxel initialization can change the working directory to the entry script's
location. Anchor resource paths explicitly instead of relying on the launch
working directory:

.. code-block:: python

   from pathlib import Path
   from loom import AssetStore

   assets = AssetStore(Path(__file__).resolve().parent / "assets")
   image.load(0, 0, str(assets.path("sprites/player.png")))
   # Keep the store alive while consumers need its paths; close on owner exit.
   assets.close()

For a normal directory or zip-imported Python package, use
``AssetStore.from_package("mygame", directory="assets")``. Zip members are
materialized once into temporary files for native loaders that require a real
path. ``close()`` removes these extracted files; filesystem assets are never
deleted. The store also supports ``with``. Namespace packages and custom
resource loaders are not supported in this initial API.

Names are portable relative POSIX file paths. Absolute names, empty segments,
``.``/``..``, backslashes and colons are rejected. Directory results and symlinks
escaping a filesystem root are rejected too. This is a convenience for trusted
application resources, not a sandbox against concurrent filesystem changes.
External deletion or modification of assets is not managed. There is no image,
font, sound or decoded-resource cache, and the store does not change cwd.

Include game assets explicitly in your wheel, Pyxel package or executable.
``AssetStore`` resolves resources already shipped with the game; it does not add
missing files to a distribution or certify a Steam build.

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

Standalone contract check
~~~~~~~~~~~~~~~~~~~~~~~~~

``tools/check_bundle.py OUTPUT`` exercises the official ``package`` then
``app2exe`` pipeline on the current operating system. Install a built Loom wheel
(non-editable) and ``pyxel[app2exe]==3.0.0`` first. ``OUTPUT`` must not exist; the
harness refuses to overwrite a previous run. Linux builders must have SDL2
installed before ``app2exe`` so PyInstaller can collect the shared library.
On Ubuntu install it with ``sudo apt-get install libsdl2-2.0-0``. The harness
requires a nonempty ``libSDL2-2.0.so.0`` inside the generated Linux artifact;
installing it only on the host is not accepted as a passing bundle check.
System libraries such as glibc remain target-OS dependencies.

It stages the installed package,
not ``src/``, alongside a finite test fixture, not another game sample.

The generated distribution is copied to a different path and its original
bundle and staging directories are renamed out of use. The relocated executable
runs twice from an unrelated working directory without
Python environment variables, ``LD_LIBRARY_PATH``, ``LD_PRELOAD``,
``LD_LIBRARY_PATH_ORIG``, ``LD_AUDIT`` or the development environment on ``PATH``. It checks
frozen-runtime and extracted-game import origins, a bundled PNG pixel and its
composited framebuffer color, scene transition
and shutdown hooks, and SaveStore readback across the two processes. Output
includes ``metrics.json`` with versions, bundle bytes and elapsed build/check
time, and separate per-run reports. These measurements have no speed threshold.
The Windows/Linux CI jobs retain build artifacts for inspection; they do not
publish a release or upload anything to Steam.

This is a build-host frozen-runtime check, not a clean-machine certification.
The host still provides operating-system libraries. Test the distribution on
fresh target machines before release, including display/audio drivers, physical
controllers, permissions and platform-specific save paths. The probe uses a
headless window and an explicit temporary save directory; it does not verify
Steamworks, Steam Cloud, Steam Deck, signing or installers.


Rendered-pixel picking
----------------------

``Viewport.to_local`` / ``to_output`` remain continuous geometric transforms.
For interaction with actual displayed pixels, use ``display.pick(x, y)`` instead:
Pyxel's fractional-scale rasterization rounds and accumulates float32 samples,
so a geometric letterbox edge need not coincide with a painted pixel edge.
``GameApp`` now supplies this discrete source-pixel pair in
``InputFrame.world_pointer`` for both integer and fit scaling. This replaces
fractional surface coordinates; use the viewport explicitly for continuous
geometry. Camera conversion still follows surface picking as a separate step.

Picking returns ``None`` outside the output or painted world coverage. Fractional
output coordinates select their containing pixel. The pinned Pyxel 3.0 sampling
model uses two compact integer arrays built only at resize, O(output width +
height) work/storage, with O(1) lookup and no per-frame scan. It assumes normal
compositing state without external screen camera, clipping or dithering changes.


Opt-in UI key repeat
--------------------

Long lists and sliders can repeat selected navigation actions without turning
physical key presses into synthetic gameplay presses:

.. code-block:: python

   from loom import ActionRepeat, UIRouter

   router = UIRouter(
       [settings_panel],
       repeat=ActionRepeat(
           {"next", "previous", "decrement", "increment"},
           delay=0.4,
           interval=0.08,
       ),
   )
   result = router.update(frame, dt=dt)
   # Gameplay receives only physical edges, filtered by normal UI ownership.
   game.update(result.remaining, dt)

Repeat is disabled by default; enabled routers require ``dt`` in seconds.
Each consumer owns its repeater. Only the four navigation names above are
accepted: confirmation, purchases and pointer actions never auto-repeat.
Repeat does not mutate ``InputFrame`` or manufacture gameplay press edges;
normal UI ownership filtering still applies.

Release, cancellation and panel/modal changes stop repeat until a fresh press.
Slider repeat cannot carry over to another focused control. Long frames do not
queue bursts, and ambiguous simultaneous inputs do not arm delayed operations.
See ``ActionRepeat`` and ``UIRouter`` API contracts for exact timing and ownership
rules. Other consumers can use ``ActionRepeat.update(frame, dt)`` to obtain
separate pulses; that lower-level helper does not infer UI ownership.


2D scrolling worlds
-------------------

``Camera2D`` translates game-world coordinates into the low-resolution surface.
``InputFrame.world_pointer`` remains surface-local; convert it explicitly after
UI routing. Letterbox points remain ``None``.

.. code-block:: python

   camera = Camera2D((320, 180), world_size=(2048, 1024))
   view = CameraView(display.world)  # One owner per drawing target.
   camera.look_at(player.x, player.y)
   local = result.remaining.world_pointer
   picked = camera.view_to_world(*local) if local is not None else None
   display.world.cls(0)
   with view.apply(camera) as image:
       image.rect(player.x, player.y, 8, 8, 7)
   display.composite()
   panel.draw(pyxel)  # Non-scrolling HUD.

Drawing and picking share an integer origin. Optional zero-origin world bounds
clamp the view or center smaller worlds. Pixel-exact ranges, rounding and
out-of-view conversion rules are documented on ``Camera2D``. There is no zoom,
rotation, automatic smoothing or physics. Gameplay picking must also respect
``result.pointer_consumed``.

``CameraView`` assumes zero native camera state outside its managed scopes and
restores its own nested offsets on exit, even on exceptions. Do not mix raw ``camera()`` calls or
other wrappers on its target, or move the camera inside a scope. After replacing
``display.world``, resize the camera and create a wrapper for the new image.

Sprite frame playback
---------------------

Share immutable clips, not playback state. Frame rectangles select regions in
a game-owned sprite sheet; Pyxel still handles drawing and source clipping.

.. code-block:: python

   from loom import SpriteClip, SpritePlayer

   walk = SpriteClip(((0, 0, 16, 16), (16, 0, 16, 16)), fps=8)
   player = SpritePlayer(walk)  # loop=False for an attack or one-shot effect.
   player.update(dt)           # Omit this while the owning scene is paused.
   image.blt(x, y, sheet, *player.frame, colkey=0)

A one-shot finishes only after the final frame's display time, then retains
that frame. ``restart()`` returns to frame zero; create another player to switch
clips. Large time steps skip directly without emitting intermediate events.
Frames have equal duration, positive dimensions and nonnegative source origins.
Asset loading, sheet bounds, flipping, per-frame events and animation state
machines remain game policy. Timeline continues to handle numeric interpolation
and delayed callbacks, separately from this discrete frame cursor.
