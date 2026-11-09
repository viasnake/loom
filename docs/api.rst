API reference
=============

Application and screens
-----------------------

.. autoclass:: loom.runtime.GameApp
   :members: run, request_quit, request_display, request_bindings, request_input_cancel

.. autoclass:: loom.app.Scene
   :members: enter, exit, pause, resume, update, draw
   :undoc-members:

.. autoclass:: loom.app.SceneStack
   :members: current, push, pop, replace, quit, update, draw, close
   :undoc-members:

Input
-----

.. autoclass:: loom.input.InputFrame
   :members: without
   :undoc-members:

.. autoclass:: loom.sticks.StickBinding
   :members: normalize

.. autoclass:: loom.input.ActionMap
   :members: sample, reset, cancel, replace_bindings, bindings, to_data, physical_held, physical_pressed, sticks
   :undoc-members:

.. autoclass:: loom.controls.BindingEditor
   :members:

.. autoclass:: loom.controls.KeyCapture
   :members:

.. autoclass:: loom.controls.CaptureResult
   :members:

Display
-------

.. autoclass:: loom.display.DisplayConfig
   :members: viewport
   :undoc-members:

.. autoclass:: loom.display.Viewport
   :members: fit, to_local, to_output
   :undoc-members:

.. autoclass:: loom.display.PyxelDisplay
   :members: resize, composite, pick

UI
--

.. autoclass:: loom.routing.UIRouter
   :members:

.. autoclass:: loom.routing.UIRouteResult

.. autoclass:: loom.canvas.PyxelCanvas
   :members: clipped, rect, text

.. autoclass:: loom.geometry.Rect
   :members: contains, intersection

.. autoclass:: loom.ui.ClippingCanvas
   :members:

.. autoclass:: loom.ui.FontCanvas
   :members:

.. autoclass:: loom.ui.ImageCanvas
   :members:

.. autoclass:: loom.ui.Icon
   :members: draw

.. autoclass:: loom.ui.Typography
   :members:


.. autoclass:: loom.ui.Column
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Button
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Toggle
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Slider
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Label
   :members:
   :undoc-members:

.. autoclass:: loom.ui.ProgressBar
   :members: value, draw

.. autoclass:: loom.ui.Theme

.. autoclass:: loom.ui.UIInput
   :members: from_frame

.. autoclass:: loom.ui.UIResult
   :members: consumed
   :undoc-members:

Time and animation
------------------

.. autoclass:: loom.timing.Timeline
   :members:

.. autoclass:: loom.timing.Tween
   :members:

.. autoclass:: loom.timing.Timer
   :members:

.. autofunction:: loom.timing.linear
.. autofunction:: loom.timing.smoothstep
.. autofunction:: loom.timing.ease_out_cubic

Audio
-----

.. autoclass:: loom.audio.AudioMixer
   :members:

.. autoclass:: loom.audio.Voice
   :members:

Colors and text
---------------

.. autoclass:: loom.palette.Palette
   :members: index, apply
   :undoc-members:

.. autoclass:: loom.text.FontCatalog
   :members: register, measure, wrap, draw, clear_cache
   :undoc-members:

Resource files
--------------

.. autoclass:: loom.assets.AssetStore
   :members:

Storage
-------

.. autoclass:: loom.storage.SaveStore
   :members: for_app, path, save, load, recover
   :undoc-members:

.. autoclass:: loom.storage.AppPaths
   :members: for_app
   :undoc-members:

.. autoexception:: loom.storage.SaveError
.. autoexception:: loom.storage.CorruptSaveError
.. autoexception:: loom.storage.FutureVersionError
.. autoexception:: loom.storage.MigrationError


Logical input repetition
------------------------

.. autoclass:: loom.ActionRepeat
   :members: actions, update, reset


2D scrolling views
------------------

.. autoclass:: loom.Camera2D
   :members: surface_size, world_size, position, origin, visible_rect, move_to, look_at, resize, world_to_view, view_to_world

.. autoclass:: loom.CameraView
   :members: apply

Sprite frame playback
---------------------

.. autoclass:: loom.SpriteClip
   :members: frames, fps, duration

.. autoclass:: loom.SpritePlayer
   :members: clip, loop, frame, index, finished, update, restart
