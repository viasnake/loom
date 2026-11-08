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
Labels can opt into width-aware text wrapping. Nested layouts are not implemented. Fonts are
supplied by the game. Audio buses own explicit channel groups and compose volume
without changing sound assets. Automatic OS focus handling and asynchronous
saves are not implemented.

Native headless tests exercise real Pyxel buffers without a physical window.
CI exercises relocated frozen artifacts on Windows and Linux. Interactive
desktop behavior, DPI, physical controllers, long-session memory and Steam/Deck
acceptance still require platform testing.
