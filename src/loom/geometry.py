"""Screen-space rectangles shared by layout and drawing adapters."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def contains(self, x: float | None, y: float | None) -> bool:
        return (
            x is not None
            and y is not None
            and self.x <= x < self.x + self.width
            and self.y <= y < self.y + self.height
        )

    def intersection(self, other: "Rect") -> "Rect":
        left = max(self.x, other.x)
        top = max(self.y, other.y)
        right = min(self.x + self.width, other.x + other.width)
        bottom = min(self.y + self.height, other.y + other.height)
        return Rect(left, top, max(0, right - left), max(0, bottom - top))
