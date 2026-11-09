"""Logical render surfaces and coordinate conversion, not OS window management."""

from array import array
from dataclasses import dataclass
from math import ceil, floor, isfinite
from struct import Struct
from typing import Any


_F32 = Struct("f")


def _f32(value: float) -> float:
    return _F32.unpack(_F32.pack(value))[0]


def _round_pixel(value: float) -> int:
    return floor(value + 0.5) if value >= 0 else ceil(value - 0.5)


def _copy_axis(source: int, position: float, scale: float) -> tuple[int, float]:
    # Even copies preserve odd source edges at even integer scales.
    size = source + source % 2
    return size, position + size * (scale - 1) / 2


def _raster_axis(
    source: int, target: int, position: float, scale: float, *, stepped: bool
) -> array:
    """Pinned Pyxel 3.0 canvas.rs TransformProjection/blit_with_transform.

    https://github.com/kitao/pyxel/blob/v3.0.0/crates/pyxel-core/src/canvas.rs

    Native x sampling accumulates float32 steps; y is recomputed for each row.
    A direct affine formula is not equivalent at pixel rounding boundaries.
    Build once on resize, not during drawing/picking. -1 denotes no source pixel.
    """
    indices = array("i", [-1]) * target
    copy_size, blit_position = _copy_axis(source, position, scale)
    half = _f32((copy_size - 1) / 2)
    native_scale = _f32(scale)
    destination = _round_pixel(_f32(blit_position))
    if native_scale == 1:
        for pixel in range(max(0, destination), min(target, destination + source)):
            indices[pixel] = pixel - destination
        return indices
    if native_scale < 2**-23:
        return indices  # Native transform rejects scales below float32 epsilon.
    center = _f32(destination + half)
    bound = _f32(_f32(half + 1) * native_scale)
    first = max(0, _round_pixel(_f32(center - bound)))
    last = min(target - 1, _round_pixel(_f32(center + bound)))
    step = _f32(1 / native_scale)
    value = _f32(half + _f32(_f32(first - center) * step))
    for pixel in range(first, last + 1):
        if not stepped:
            value = _f32(half + _f32(_f32(pixel - center) * step))
        index = _round_pixel(value)
        if 0 <= index < source:
            indices[pixel] = index
        value = _f32(value + step)
    return indices


def _raster_indices(viewport):
    w, h = viewport.source_size
    tw, th = viewport.target_size
    return (
        _raster_axis(w, tw, viewport.x, viewport.scale, stepped=True),
        _raster_axis(h, th, viewport.y, viewport.scale, stepped=False),
    )


def _size(value: tuple[int, int]) -> None:
    if len(value) != 2 or any(type(n) is not int or n <= 0 for n in value):
        raise ValueError("size must contain two positive integers")


@dataclass(frozen=True, slots=True)
class Viewport:
    """Aspect-preserving rectangle with copied, immutable size tuples.

    Coordinates are Pyxel screen pixels, not DPI pixels.
    """

    source_size: tuple[int, int]
    target_size: tuple[int, int]
    scale: float
    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_size", tuple(self.source_size))
        object.__setattr__(self, "target_size", tuple(self.target_size))

    @classmethod
    def fit(
        cls,
        source_size: tuple[int, int],
        target_size: tuple[int, int],
        *,
        integer: bool = True,
    ) -> "Viewport":
        _size(source_size)
        _size(target_size)
        scale = min(target_size[0] / source_size[0], target_size[1] / source_size[1])
        # Integer-fit never silently crops. A too-small target must be made larger.
        if integer:
            if scale < 1:
                raise ValueError(
                    "integer scaling requires a target at least as large as the source"
                )
            scale = float(floor(scale))
        x = (target_size[0] - source_size[0] * scale) / 2
        y = (target_size[1] - source_size[1] * scale) / 2
        if integer:
            # Put an odd spare pixel at the right/bottom, never at half a pixel.
            x, y = floor(x), floor(y)
        return cls(source_size, target_size, scale, x, y)

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
        if not (
            self.x <= x < self.x + self.width and self.y <= y < self.y + self.height
        ):
            return None
        return (x - self.x) / self.scale, (y - self.y) / self.scale

    def to_output(self, x: float, y: float) -> tuple[float, float]:
        return self.x + x * self.scale, self.y + y * self.scale


@dataclass(frozen=True, slots=True)
class DisplayConfig:
    """Render settings; size sequences are copied into immutable tuples."""

    output_size: tuple[int, int] = (960, 540)
    world_size: tuple[int, int] = (320, 180)
    scale: str = "integer"

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_size", tuple(self.output_size))
        object.__setattr__(self, "world_size", tuple(self.world_size))
        if self.scale not in ("integer", "fit"):
            raise ValueError("scale must be 'integer' or 'fit'")
        self.viewport()

    def viewport(self) -> Viewport:
        return Viewport.fit(
            self.world_size, self.output_size, integer=self.scale == "integer"
        )


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
        self._pick_x, self._pick_y = _raster_indices(self.viewport)

    def resize(self, config: DisplayConfig) -> None:
        """Apply between frames. Unchanged world buffers are reused."""
        viewport = config.viewport()
        pick_x, pick_y = _raster_indices(viewport)
        world = self.world
        if config.world_size != self.config.world_size:
            world = self.pyxel.Image(*config.world_size)
        if config.output_size != self.config.output_size:
            self.pyxel.resize(*config.output_size)
        self.config, self.viewport, self.world = config, viewport, world
        self._pick_x, self._pick_y = pick_x, pick_y

    def pick(self, x: float, y: float) -> tuple[int, int] | None:
        """Pick the source pixel actually displayed at an output pixel.

        Fractional output coordinates select their containing pixel (floor).
        Nonfinite/outside-output/letterbox points return None. This discrete
        Pyxel 3.0 raster mapping differs from Viewport's continuous geometry.
        Compact axis tables cost O(output width + height) at resize; lookup is
        O(1). Assumes normal composite state: no external camera/clip/dithering.
        """
        if not (isfinite(x) and isfinite(y)):
            return None
        width, height = self.config.output_size
        if not (0 <= x < width and 0 <= y < height):
            return None
        source_x, source_y = self._pick_x[floor(x)], self._pick_y[floor(y)]
        if source_x < 0 or source_y < 0:
            return None
        return source_x, source_y

    def composite(self, clear_color: int = 0) -> None:
        self.pyxel.cls(clear_color)
        w, h = self.config.world_size
        viewport = self.viewport
        # Pyxel 3 scales around the copy rectangle's centre. An odd-sized copy
        # loses an edge pixel at even integer scales. An even copy rectangle
        # avoids that rounding; Pyxel clips its excess to the actual Image.
        copy_width, x = _copy_axis(w, viewport.x, viewport.scale)
        copy_height, y = _copy_axis(h, viewport.y, viewport.scale)
        self.pyxel.blt(
            x, y, self.world, 0, 0, copy_width, copy_height, scale=viewport.scale
        )
