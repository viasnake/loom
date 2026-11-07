"""Named font resources and bounded measurement/wrapping caches.

Fonts are supplied by the game (e.g. pyxel.Font(path, size)); no fonts, licenses,
IME or language-specific line-breaking rules are implicitly bundled.
"""
from collections import OrderedDict
from typing import Any


class FontCatalog:
    def __init__(self, max_entries: int = 256) -> None:
        if type(max_entries) is not int or max_entries < 0:
            raise ValueError("max_entries must be a non-negative integer")
        self.max_entries = max_entries
        self._fonts: dict[str, tuple[Any, int]] = {"default": (None, 6)}
        self._cache: OrderedDict[tuple, Any] = OrderedDict()

    def register(self, name: str, font: Any = None, *, line_height: int = 6) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("font name must be non-empty")
        if type(line_height) is not int or line_height <= 0:
            raise ValueError("line_height must be positive")
        if font is not None and not callable(getattr(font, "text_width", None)):
            raise TypeError("font must provide text_width")
        self._fonts[name] = (font, line_height)
        self._cache.clear()

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()

    def _cached(self, key: tuple, create: Any) -> Any:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        value = create()
        if self.max_entries:
            self._cache[key] = value
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return value

    def measure(self, text: str, font: str = "default") -> tuple[int, int]:
        face, height = self._fonts[font]
        def measure_lines() -> tuple[int, int]:
            lines = text.split("\n")
            widths = [face.text_width(line) if face is not None else len(line) * 4 for line in lines]
            return max(widths, default=0), len(lines) * height
        return self._cached(("measure", font, text), measure_lines)

    def wrap(self, text: str, width: int, font: str = "default") -> tuple[str, ...]:
        """Greedy wrapping at whitespace, splitting long words at code points.

        Explicit newlines and blank lines are retained. Not Japanese kinsoku or
        grapheme-aware layout; choose a suitable font and perform richer shaping
        in the game when needed. A glyph wider than width occupies its own line.
        """
        if type(width) is not int or width <= 0:
            raise ValueError("width must be a positive integer")
        self._fonts[font]  # validate even for an empty string
        def wrap_lines() -> tuple[str, ...]:
            result: list[str] = []
            for paragraph in text.split("\n"):
                line = ""
                for word in paragraph.split():
                    candidate = f"{line} {word}" if line else word
                    if self.measure(candidate, font)[0] <= width:
                        line = candidate
                        continue
                    if line:
                        result.append(line)
                        line = ""
                    for char in word:
                        if line and self.measure(line + char, font)[0] > width:
                            result.append(line)
                            line = ""
                        line += char
                result.append(line)
            return tuple(result)
        return self._cached(("wrap", font, text, width), wrap_lines)

    def draw(self, target: Any, x: float, y: float, text: str, color: int,
             font: str = "default") -> None:
        face, line_height = self._fonts[font]
        for line in text.split("\n"):
            target.text(x, y, line, color, font=face)
            y += line_height
