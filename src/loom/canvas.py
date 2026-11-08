"""A small Pyxel canvas with explicitly owned, nestable clipping."""

from contextlib import contextmanager
from typing import Any, Iterator

from .geometry import Rect


class PyxelCanvas:
    """Adapt a Pyxel module or Image to UI drawing and scoped clipping.

    Pyxel has no clip getter. This adapter owns clipping while drawing: use
    ``clipped()`` instead of calling the target's ``clip`` directly. An outer
    managed clip is intersected and restored even when a widget raises.
    Outside a scope the target is assumed to have its full surface available.
    """

    def __init__(self, target: Any):
        self.target = target
        self._clip: Rect | None = None

    def rect(self, x: int, y: int, w: int, h: int, col: int) -> None:
        self.target.rect(x, y, w, h, col)

    def text(self, x: int, y: int, text: str, col: int, *, font: Any = None) -> None:
        self.target.text(x, y, text, col, font=font)

    @contextmanager
    def clipped(self, bounds: Rect) -> Iterator[None]:
        """Temporarily intersect the current managed clip with bounds."""
        if bounds.width < 0 or bounds.height < 0:
            raise ValueError("clip dimensions must be non-negative")
        previous = self._clip
        surface = Rect(0, 0, self.target.width, self.target.height)
        active = surface if previous is None else previous.intersection(surface)
        current = active.intersection(bounds)
        self.target.clip(current.x, current.y, current.width, current.height)
        self._clip = current
        try:
            yield
        finally:
            self._clip = previous
            if previous is None:
                self.target.clip()
            else:
                self.target.clip(
                    previous.x, previous.y, previous.width, previous.height
                )
