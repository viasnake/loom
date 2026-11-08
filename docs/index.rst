Loom
====

A lightweight game framework on Pyxel 3.0. Loom manages screens, UI input,
render surfaces and persistence. Games own their rules; Pyxel and Cube provide
rendering and 3D physics.

.. toctree::
   :maxdepth: 2

   getting-started
   api

Status
------

This is an early alpha. UI includes flat columns, buttons, toggles, sliders and
optional vertical viewports. Input settings support capture and explicit conflict
resolution. Scene-owned timelines provide numeric animation and delayed work.
Nested layouts and automatic text wrapping are not implemented. Fonts are
supplied by the game. Automatic OS focus handling, audio buses and asynchronous
saves are not implemented.

Native headless tests exercise real Pyxel buffers without a physical window.
Windows executable launch, DPI, physical controllers, long-session memory and
Steam/Deck acceptance still require platform testing.
