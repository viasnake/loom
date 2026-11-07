API reference
=============

Application and screens
-----------------------

.. autoclass:: loom.runtime.GameApp
   :members: run, request_quit, request_display

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

.. autoclass:: loom.input.ActionMap
   :members: sample, reset
   :undoc-members:

Display
-------

.. autoclass:: loom.display.DisplayConfig
   :members: viewport
   :undoc-members:

.. autoclass:: loom.display.Viewport
   :members: fit, to_local, to_output
   :undoc-members:

.. autoclass:: loom.display.PyxelDisplay
   :members: resize, composite

UI
--

.. autoclass:: loom.ui.Column
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Button
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Label
   :members:
   :undoc-members:

.. autoclass:: loom.ui.Theme

.. autoclass:: loom.ui.UIInput

.. autoclass:: loom.ui.UIResult
   :members: consumed
   :undoc-members:

Colors and text
---------------

.. autoclass:: loom.palette.Palette
   :members: index, apply
   :undoc-members:

.. autoclass:: loom.text.FontCatalog
   :members: register, measure, wrap, draw, clear_cache
   :undoc-members:

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
