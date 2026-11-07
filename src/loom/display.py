"""Logical render surfaces and coordinate conversion, not OS window management."""
from dataclasses import dataclass
from math import floor, isfinite
from typing import Any


def _size(value: tuple[int, int]) -> None:
    if len(value) != 2 or any(type(n) is not int or n <= 0 for n in value):
        raise ValueError("size must contain two positive integers")


@dataclass(frozen=True, slots=True)
class Viewport:
    """Aspect-preserving rectangle. Coordinates are Pyxel screen pixels, not DPI pixels."""

    source_size: tuple[int, int]
    target_size: tuple[int, int]
    scale: float
    x: float
    y: float

    @classmethod
    def fit(cls, source_size: tuple[int, int], target_size: tuple[int, int],
            *, integer: bool = True) -> "Viewport":
        _size(source_size)
        _size(target_size)
        scale = min(target_size[0] / source_size[0], target_size[1] / source_size[1])
        # Integer-fit never silently crops. A too-small target must be made larger.
        if integer:
            if scale < 1:
                raise ValueError("integer scaling requires a target at least as large as the source")
            scale = float(floor(scale))
        return cls(source_size, target_size, scale,
                   (target_size[0] - source_size[0] * scale) / 2,
                   (target_size[1] - source_size[1] * scale) / 2)

    @property
    def width(self) -> float:
        return self.source_size[0] * self.scale

    @property
    def height(self) -> float:
        return self.source_size[1] * self.scale

    def to_local(self, x: float, y: float) -> tuple[float, float] | None:
        """Return None in letterbox margins; the right and bottom edges are exclusive."""
        if not (isfinite(x) and isfinite(y)):
            return None
        if not (self.x <= x < self.x + self.width and self.y <= y < self.y + self.height):
            return None
        return (x - self.x) / self.scale, (y - self.y) / self.scale

    def to_output(self, x: float, y: float) -> tuple[float, float]:
        return self.x + x * self.scale, self.y + y * self.scale


@dataclass(frozen=True, slots=True)
class DisplayConfig:
    output_size: tuple[int, int] = (960, 540)
    world_size: tuple[int, int] = (320, 180)
    scale: str = "integer"

    def __post_init__(self) -> None:
        if self.scale not in ("integer", "fit"):
            raise ValueError("scale must be 'integer' or 'fit'")
        self.viewport()

    def viewport(self) -> Viewport:
        return Viewport.fit(self.world_size, self.output_size, integer=self.scale == "integer")


class PyxelDisplay:
    """One reused low-resolution world Image, composited before high-resolution UI.

    Construct after pyxel.init with output_size. Pyxel mouse_x/y are already screen
    coordinates: do not apply OS DPI scaling again. This does not manage physical
    window dimensions or enumerate monitor modes.
    """

    def __init__(self, pyxel: Any, config: DisplayConfig = DisplayConfig()) -> None:
        self.pyxel = pyxel
        self.config = config
        self.viewport = config.viewport()
        self.world = pyxel.Image(*config.world_size)

    def resize(self, config: DisplayConfig) -> None:
        """Apply between frames. Unchanged world buffers are reused."""
        viewport = config.viewport()
        world = self.world if config.world_size == self.config.world_size else self.pyxel.Image(*config.world_size)
        if config.output_size != self.config.output_size:
            self.pyxel.resize(*config.output_size)
        self.config, self.viewport, self.world = config, viewport, world

    def composite(self, clear_color: int = 0) -> None:
        self.pyxel.cls(clear_color)
        w, h = self.config.world_size
        viewport = self.viewport
        # Pyxel scales about the original copy rectangle's centre, not top-left.
        x = viewport.x + (viewport.width - w) / 2
        y = viewport.y + (viewport.height - h) / 2
        self.pyxel.blt(x, y, self.world, 0, 0, w, h, scale=viewport.scale)
