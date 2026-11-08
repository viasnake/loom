"""Translation-only 2D world views and explicitly owned native camera scopes."""

from contextlib import contextmanager
from math import floor, isfinite
from typing import Any, Iterator

from .geometry import Rect

_PIXEL_LIMIT = 2**24  # Pyxel native coordinates pass through float32.


def _point(x: float, y: float) -> tuple[float, float]:
    try:
        if any(type(v) not in (int, float) or not isfinite(v) for v in (x, y)):
            raise ValueError
        return float(x), float(y)
    except (ValueError, OverflowError):
        raise ValueError("coordinates must be finite numbers") from None


def _size(value: tuple[int, int]) -> tuple[int, int]:
    size = tuple(value)
    if len(size) != 2 or any(
        type(n) is not int or not 0 < n <= _PIXEL_LIMIT for n in size
    ):
        raise ValueError(
            "surface/world sizes must contain two positive integers no greater than 2**24"
        )
    return size


def _origin(position, size) -> tuple[int, int]:
    # Explicit integer snapping avoids native float32 rounding of camera input.
    result = []
    for value, extent in zip(position, size):
        magnitude = abs(value)
        whole = floor(magnitude)
        snapped = whole + (magnitude - whole >= 0.5)
        if value < 0:
            snapped = -snapped
        if snapped < -_PIXEL_LIMIT or snapped + extent > _PIXEL_LIMIT:
            raise ValueError(
                "camera view must remain within pixel-exact +/-2**24 coordinates"
            )
        result.append(snapped)
    return tuple(result)


class Camera2D:
    """A surface-sized window onto a world; no zoom, rotation or follow timing.

    position is the clamped fractional top-left; origin is its pixel-snapped
    counterpart used by both drawing and coordinate conversion. Optional
    world_size bounds a world starting at (0, 0). An axis smaller than the
    surface is centered rather than stretched. Sizes are positive integers up to
    2**24. Snapped origin and far view edges must stay within +/-2**24, where
    native float32 retains integer pixels.
    Loom snaps explicitly before passing integers to Pyxel; it does not emulate
    every rounding detail of passing fractional values directly to Image.camera.
    Resize retains the current position, clamping it to the new visible extent.
    Mutate via move_to/look_at/resize, not while a CameraView scope is active.
    """

    def __init__(
        self,
        surface_size: tuple[int, int],
        *,
        world_size: tuple[int, int] | None = None,
        position: tuple[float, float] = (0, 0),
    ):
        self._surface_size = _size(surface_size)
        self._world_size = None if world_size is None else _size(world_size)
        self.move_to(*position)

    @property
    def surface_size(self) -> tuple[int, int]:
        return self._surface_size

    @property
    def world_size(self) -> tuple[int, int] | None:
        return self._world_size

    @property
    def position(self) -> tuple[float, float]:
        return self._position

    @property
    def origin(self) -> tuple[int, int]:
        return self._origin

    @property
    def visible_rect(self) -> Rect:
        """Surface coverage in world pixels, including margins of a small world."""
        return Rect(*self.origin, *self.surface_size)

    def _clamp(self, position, size):
        if self.world_size is None:
            return position
        return tuple(
            (
                (world - surface) / 2
                if world < surface
                else min(max(value, 0), world - surface)
            )
            for value, surface, world in zip(position, size, self.world_size)
        )

    def move_to(self, x: float, y: float) -> None:
        position = self._clamp(_point(x, y), self.surface_size)
        origin = _origin(position, self.surface_size)
        self._position, self._origin = position, origin

    def look_at(self, x: float, y: float) -> None:
        """Center immediately; the game owns follow/smoothing policy."""
        x, y = _point(x, y)
        self.move_to(x - self.surface_size[0] / 2, y - self.surface_size[1] / 2)

    def resize(self, surface_size: tuple[int, int]) -> None:
        size = _size(surface_size)
        position = self._clamp(self.position, size)
        origin = _origin(position, size)
        self._surface_size, self._position, self._origin = size, position, origin

    def world_to_view(self, x: float, y: float) -> tuple[float, float]:
        """Convert to surface coordinates, without clipping offscreen points."""
        x, y = _point(x, y)
        return _point(x - self.origin[0], y - self.origin[1])

    def view_to_world(self, x: float, y: float) -> tuple[float, float] | None:
        """Convert a surface point; outside/right/bottom edges return None.

        Coordinates in small-world margins still map to world space. World
        collision/picking remains the game's responsibility. Filter letterbox
        None from Viewport.to_local before calling this method.
        """
        x, y = _point(x, y)
        if not (0 <= x < self.surface_size[0] and 0 <= y < self.surface_size[1]):
            return None
        return _point(x + self.origin[0], y + self.origin[1])


class CameraView:
    """Own one target's drawing-camera state, initially assumed to be zero.

    Keep one wrapper per Pyxel Image/module. Nested apply scopes through that
    wrapper restore its preceding offset even on exceptions; the outer scope
    restores zero. Pyxel has no camera getter: external camera() calls or other
    wrappers on the same target invalidate this contract. This does not own
    clipping or palette state. Draw high-resolution UI outside the scope.
    """

    def __init__(self, target: Any):
        self.target = target
        self._origin = (0, 0)

    @contextmanager
    def apply(self, camera: Camera2D) -> Iterator[Any]:
        """Apply a snapshot of camera.origin for this drawing scope."""
        if (self.target.width, self.target.height) != camera.surface_size:
            raise ValueError("camera surface_size must match the drawing target")
        previous = self._origin
        self.target.camera(*camera.origin)
        self._origin = camera.origin
        try:
            yield self.target
        finally:
            self._origin = previous
            self.target.camera(*previous)
