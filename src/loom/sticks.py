"""Signed 2D stick normalization, independent of engine polling."""

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True, slots=True)
class StickBinding:
    """A signed SDL-style 2D stick, not triggers or automatic UI navigation.

    Input codes are read exclusively through btnv. Raw -32768..32767 values are
    clamped and normalized asymmetrically. A radial deadzone rescales the usable
    range continuously, and diagonal magnitude is limited to one.
    """

    x: int
    y: int
    deadzone: float = 0.2
    invert_x: bool = False
    invert_y: bool = False

    def __post_init__(self):
        if (
            any(type(code) is not int or code < 0 for code in (self.x, self.y))
            or self.x == self.y
        ):
            raise ValueError("stick axes must be distinct nonnegative integer codes")
        if type(self.deadzone) not in (int, float) or not 0 <= self.deadzone < 1:
            raise ValueError("deadzone must be a finite number in [0, 1)")
        if type(self.invert_x) is not bool or type(self.invert_y) is not bool:
            raise TypeError("axis inversion flags must be bools")

    def normalize(self, x: int, y: int) -> tuple[float, float]:
        if type(x) is not int or type(y) is not int:
            raise ValueError("raw stick values must be integers")

        def axis(raw):
            raw = max(-32768, min(32767, raw))
            return raw / (32768 if raw < 0 else 32767)

        x, y = axis(x), axis(y)
        if self.invert_x:
            x = -x
        if self.invert_y:
            y = -y
        length = hypot(x, y)
        if length <= self.deadzone:
            return (0.0, 0.0)
        magnitude = (min(length, 1.0) - self.deadzone) / (1 - self.deadzone)
        return (x / length * magnitude, y / length * magnitude)
