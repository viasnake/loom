# Design boundary

Loom is a reusable game-building layer, not a general engine replacement.

```
game rules / saves / scenes
          |          |
      Loom primitives ----- game drawing -> Pyxel / Cube
          |
      Pyxel runtime adapter
```

Pure input, scene, layout, palette and storage tests do not import Pyxel. Game
renderers may call Pyxel directly; an imaginary all-engine rendering API would
add cost without demonstrating reuse. No framework module imports a sample.

## Frame contract

1. Read physical keys once and resolve named actions.
2. Deliver input only to the top screen. The screen lets its UI consume events.
3. Update unblocked lower scenes without input, then the top scene.
4. Apply one queued scene change and any requested render-size change.
5. Draw visible scenes bottom to top. Draw cannot request scene changes.

Scene hooks own their resources; `exit` releases them. Pause overlays default to
blocking updates. Non-opaque overlays retain lower rendering. A close-click is
never sent into the newly exposed scene in that update. Pyxel can terminate the
process, so application-requested quit runs hooks before calling it. Forced OS
termination is not a graceful-shutdown guarantee.

## Resolution and colors

The initial compositor uses one reusable world Image and the screen. World and
UI are logically distinct but share Pyxel's global palette. Integer fit rejects
an output smaller than the world instead of silently cropping. Fit mode permits
fractional downscale. Physical DPI and monitor mode selection are not claimed.

Names are resolved to palette indices at setup. Fonts and bounded measurements
are reused. There is no per-frame palette assignment or UI tree rebuilding.
Changing a Cube palette requires its shading table to be rebuilt by its owner.

## Delivery phases

1. Current alpha: minimal vertical slice, real 2D and Cube rendering, UI-driven
   navigation, temporary save/load and pure regression tests.
2. Add nested/scrolling UI, theme/font integration and focus/rebinding handling
   using concrete sample needs. Include clipping and large visible-list tests.
3. Run Windows `app2exe` on Windows, then launch on a clean machine without
   Python. Verify DPI 100/150/200%, fullscreen/Alt-Tab, controller navigation,
   stable save paths and upgrade/recovery. Linux/Deck follows, not assumed.
4. Add optional Steam API integrations only where a game requires them. Steam
   sale does not itself require Steamworks API integration.

No schedule or completed support is implied by this roadmap. Preserve low
baseline overhead with direct-Pyxel comparisons, not claimed FPS from automated
fixed-tick recordings.

## Sources

- [Pyxel 3.0 API](https://github.com/kitao/pyxel/blob/v3.0.0/python/pyxel/__init__.pyi)
- [Cube](https://github.com/kitao/pyxel/blob/v3.0.0/docs/user-guide-cube.md)
- [Distribution](https://github.com/kitao/pyxel/blob/v3.0.0/docs/user-guide.md#distributing-applications)
- [Steamworks API](https://partner.steamgames.com/doc/sdk/api)
