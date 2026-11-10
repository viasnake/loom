"""Named font resources and bounded measurement/wrapping caches.

Fonts are supplied by the game (e.g. pyxel.Font(path, size)); no fonts, licenses,
IME or full language-specific layout are implicitly bundled.
"""

from collections import OrderedDict
from typing import Any


def _wrap_fixed(text: str, width: int) -> tuple[str, ...]:
    """Wrap the built-in 4-pixel font without measuring growing prefixes."""
    capacity = width // 4
    chunk_size = max(1, capacity)
    result: list[str] = []
    for paragraph in text.split("\n"):
        pieces: list[str] = []
        length = 0
        for word in paragraph.split():
            candidate_length = length + bool(pieces) + len(word)
            if candidate_length <= capacity:
                pieces.append(word)
                length = candidate_length
                continue
            if pieces:
                result.append(" ".join(pieces))
            # Keep the final chunk open: the next word may fit beside it.
            for start in range(0, len(word) - chunk_size, chunk_size):
                result.append(word[start : start + chunk_size])
            tail_start = ((len(word) - 1) // chunk_size) * chunk_size
            pieces = [word[tail_start:]]
            length = len(pieces[0])
        result.append(" ".join(pieces))
    return tuple(result)


# Deliberately small punctuation policy, not a Unicode/JIS line-break engine.
_NO_LINE_START = frozenset("、。，．！？：；)]}）］｝〉》」』】〕〗〙〛")
_NO_LINE_END = frozenset("([{（［｛〈《「『【〔〖〘〚")


def _wrap_japanese_punctuation(
    text: str, width: int, measure: Any = None
) -> tuple[str, ...]:
    """Prefer whitespace, then legal punctuation boundaries, within the width.

    Stop at the first overflowing prefix. If no legal boundary fits, fall back
    to that prefix's preceding code point (or one oversized glyph).
    """
    result: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = " ".join(paragraph.split())
        start = 0
        if not paragraph:
            result.append("")
        while start < len(paragraph):
            end = start
            legal = space = 0
            while end < len(paragraph):
                # Do not measure trailing separator spaces: they are discarded
                # at a break, and custom widths need not be monotonic.
                visible_end = end if paragraph[end] == " " else end + 1
                measured = (
                    (visible_end - start) * 4
                    if measure is None
                    else measure(paragraph[start:visible_end])
                )
                if measured > width:
                    break
                end += 1
                if end == len(paragraph):
                    break
                previous = end - 1
                if paragraph[previous] == " ":
                    previous -= 1
                if (
                    paragraph[end] != " "
                    and paragraph[previous] not in _NO_LINE_END
                    and paragraph[end] not in _NO_LINE_START
                ):
                    legal = end
                    if paragraph[end - 1] == " ":
                        space = end
            if end == len(paragraph):
                cut = end
            else:
                cut = space or legal or max(start + 1, end)
            result.append(paragraph[start:cut].rstrip())
            start = cut
            if start < len(paragraph) and paragraph[start] == " ":
                start += 1
    return tuple(result)


class FontCatalog:
    def __init__(self, max_entries: int = 256) -> None:
        if type(max_entries) is not int or max_entries < 0:
            raise ValueError("max_entries must be a non-negative integer")
        self.max_entries = max_entries
        self._fonts: dict[str, tuple[Any, int]] = {"default": (None, 6)}
        self._cache: OrderedDict[tuple, Any] = OrderedDict()
        self._revision = 0

    def register(self, name: str, font: Any = None, *, line_height: int = 6) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("font name must be non-empty")
        if type(line_height) is not int or line_height <= 0:
            raise ValueError("line_height must be positive")
        if font is not None and not callable(getattr(font, "text_width", None)):
            raise TypeError("font must provide text_width")
        self._fonts[name] = (font, line_height)
        self._revision += 1
        self._cache.clear()

    @property
    def revision(self) -> int:
        """Changes when font registrations change, not when caches are cleared."""
        return self._revision

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
        """Return width and line-box height; an empty string is one empty line.

        The built-in font uses a 4-pixel advance and a 6-pixel line box.
        Register a font with suitable glyph coverage for non-ASCII text.
        """
        face, height = self._fonts[font]

        def measure_lines() -> tuple[int, int]:
            lines = text.split("\n")
            widths = [
                face.text_width(line) if face is not None else len(line) * 4
                for line in lines
            ]
            return max(widths, default=0), len(lines) * height

        return self._cached(("measure", font, text), measure_lines)

    def wrap(
        self,
        text: str,
        width: int,
        font: str = "default",
        *,
        japanese_punctuation: bool = False,
    ) -> tuple[str, ...]:
        """Greedy wrapping at whitespace, splitting long words at code points.

        Explicit newlines and blank lines are retained; other whitespace is
        collapsed to single spaces. ``japanese_punctuation=True`` avoids a small,
        documented set of punctuation boundaries when they fit. Width wins if
        none fit; explicit newlines always win. This is not full kinsoku or
        grapheme-aware layout; choose a suitable font and perform richer shaping
        in the game when needed. A glyph wider than width occupies its own line.

        Only the final wrapped result enters the shared cache. Custom prefix
        widths use a temporary cache bounded by max_entries. The built-in
        fixed-width path does linear work. Custom fonts retain exact prefix
        measurement semantics (no additive or monotonic width assumption), so
        a long unbroken token can still require quadratic measurement work.
        """
        if type(japanese_punctuation) is not bool:
            raise TypeError("japanese_punctuation must be a bool")
        if type(width) is not int or width <= 0:
            raise ValueError("width must be a positive integer")
        face, _ = self._fonts[font]  # validate even for an empty string

        def wrap_lines() -> tuple[str, ...]:
            if face is None:
                if japanese_punctuation:
                    return _wrap_japanese_punctuation(text, width)
                return _wrap_fixed(text, width)
            widths: OrderedDict[str, int] = OrderedDict()

            def measure(candidate: str) -> int:
                if candidate in widths:
                    widths.move_to_end(candidate)
                    return widths[candidate]
                measured = face.text_width(candidate)
                if self.max_entries:
                    widths[candidate] = measured
                    if len(widths) > self.max_entries:
                        widths.popitem(last=False)
                return measured

            if japanese_punctuation:
                return _wrap_japanese_punctuation(text, width, measure)
            result: list[str] = []
            for paragraph in text.split("\n"):
                line = ""
                for word in paragraph.split():
                    candidate = f"{line} {word}" if line else word
                    if measure(candidate) <= width:
                        line = candidate
                        continue
                    if line:
                        result.append(line)
                        line = ""
                    for char in word:
                        if line and measure(line + char) > width:
                            result.append(line)
                            line = ""
                        line += char
                result.append(line)
            return tuple(result)

        return self._cached(
            ("wrap", font, text, width, japanese_punctuation), wrap_lines
        )

    def draw(
        self,
        target: Any,
        x: float,
        y: float,
        text: str,
        color: int,
        font: str = "default",
    ) -> None:
        face, line_height = self._fonts[font]
        for line in text.split("\n"):
            target.text(x, y, line, color, font=face)
            y += line_height
