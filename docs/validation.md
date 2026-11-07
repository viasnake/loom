# Initial alpha validation

Measured in this task on Linux x86_64, Python 3.12.14, Pyxel 3.0.0. These are
small synthetic samples, not game performance targets or Windows results.

## Passed

- 51 unittest cases: scene transitions/input ownership, scaling/margins,
  palettes/fonts, retained UI capture/focus, corrupt/future/failed saves,
  migration/backup/recovery, runtime world-pointer conversion and quit cleanup.
- Native headless menu navigation into 2D arcade, turn-based/save and Cube
  screens, pause/return, temporary save/load, 120 updates/draws per sample.
- Actual framebuffer snapshots inspected: Cube visible; 320×180 low-resolution
  world with 960×540 text. Japanese text was rendered with the machine's
  NotoSansCJK-Regular.ttc at 18px (not distributed with Loom).
- GameApp native callbacks, deferred output resize and pre-quit cleanup.
- Official `pyxel package` produced a ~16 KiB `.pyxapp` for the showcase.
  This is not a standalone EXE and excludes Python/Pyxel.

## Measurements

`tools/benchmark.py`: 1,000 warmups + 10,000 samples, no drawing:

| Operation | p50 | p95 |
|---|---:|---:|
| Direct empty scene update | 0.10 µs | 0.12 µs |
| SceneStack empty update | 0.28 µs | 0.31 µs |
| Retained UI, 20 buttons | 1.83 µs | 1.92 µs |

The 20-button panel performed one layout pass. In this short test the second
10,000 updates added zero retained Python bytes reported by tracemalloc. This
is not evidence of zero native allocations or long-session leak freedom.

Native headless 960×540 output / 320×180 world:

| Sample | update + draw p50 | p95 |
|---|---:|---:|
| Arcade | 3.26 ms | 3.65 ms |
| Turn-based | 3.09 ms | 3.42 ms |
| Cube | 3.26 ms | 4.01 ms |

Process peak RSS was ~19.9 MiB without screen capture or Japanese font loading.
These numbers include Pyxel and the sample, not just framework overhead. There
is no OS presentation, audio output or input latency measurement here.

## Still open

Windows packaged startup without Python, OS close events, Alt-Tab/focus recovery,
physical gamepad and DPI testing, long-running memory, complete UI widget/layout
coverage and Steam/Deck acceptance. A successful headless or CI test is not a
substitute for these checks. The current UI is intentionally a small subset.
