# Loom

A lightweight, code-first game framework for **Pyxel 3.0 and Python 3.11+**.
Scenes, retained UI, named input, resolution scaling, palettes and safe JSON
saves. Game rules and drawing remain yours.

Loom is an early alpha. Windows executable launch, physical controllers, DPI
and Steam integration are not yet verified.

## Run

```sh
python -m pip install -e .
python examples/showcase.py
```

The showcase includes arcade, turn-based/save and Cube screens. Use the mouse,
Tab/D-pad and Enter/A; Escape/B returns. Progress is written only by Save.

## Develop

```sh
python -m unittest discover -s tests -v
python tools/smoke.py
python tools/runtime_smoke.py
python tools/benchmark.py
```

Smoke tests use native headless Pyxel, not a physical display.

## Documentation

The [guide](docs/getting-started.rst) and [API reference](docs/api.rst) form a
Sphinx site with the Shibuya theme. Build locally:

```sh
python -m pip install -e '.[docs]'
python -m sphinx -W --keep-going -b html docs docs/_build/html
```
