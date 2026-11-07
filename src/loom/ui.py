"""Small retained UI with explicit input ownership and invalidation.

Coordinates are already in UI logical pixels. Convert at the display adapter,
not inside widgets. Text uses the canvas' configured font; this module neither
loads fonts nor changes the global palette.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol


class Canvas(Protocol):
    def rect(self, x: int, y: int, w: int, h: int, col: int) -> None: ...
    def text(self, x: int, y: int, s: str, col: int) -> None: ...


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


@dataclass(frozen=True, slots=True)
class Theme:
    """Resolved palette indices. No per-frame name lookup is needed."""

    panel: int = 1
    button: int = 5
    hover: int = 13
    text: int = 7
    disabled: int = 6
    focus: int = 10
    pressed: int = 12


@dataclass(frozen=True, slots=True)
class UIInput:
    x: float | None = None
    y: float | None = None
    pointer_pressed: bool = False
    pointer_released: bool = False
    confirm: bool = False
    next_focus: bool = False
    previous_focus: bool = False
    cancel: bool = False
    reset: bool = False


@dataclass(frozen=True, slots=True)
class UIResult:
    pointer_consumed: bool = False
    keyboard_consumed: bool = False
    cancelled: bool = False

    @property
    def consumed(self) -> bool:
        return self.pointer_consumed or self.keyboard_consumed


class Widget:
    """A widget belongs to at most one Column. Height/visibility invalidate layout."""

    focusable = False

    def __init__(self, *, height: int, visible: bool = True, enabled: bool = True):
        if height <= 0:
            raise ValueError("height must be positive")
        self._height = height
        self._visible = visible
        self.enabled = enabled
        self.rect = Rect(0, 0, 0, 0)
        self._owner: Column | None = None

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        if value <= 0:
            raise ValueError("height must be positive")
        if value != self._height:
            self._height = value
            self._invalidate()

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        if value != self._visible:
            self._visible = value
            self._invalidate()

    def _invalidate(self) -> None:
        if self._owner is not None:
            self._owner.invalidate()

    def draw(
        self,
        canvas: Canvas,
        theme: Theme,
        *,
        focused: bool,
        hovered: bool,
        pressed: bool,
    ) -> None:
        raise NotImplementedError


class Label(Widget):
    def __init__(self, text: str, *, height: int = 12, color: int | None = None):
        super().__init__(height=height)
        self.text = text
        self.color = color

    def draw(self, canvas: Canvas, theme: Theme, **_: bool) -> None:
        canvas.text(
            self.rect.x,
            self.rect.y,
            self.text,
            theme.text if self.color is None else self.color,
        )


class Button(Widget):
    focusable = True

    def __init__(
        self,
        text: str,
        on_click: Callable[[], None],
        *,
        height: int = 20,
        enabled: bool = True,
    ):
        super().__init__(height=height, enabled=enabled)
        self.text = text
        self.on_click = on_click

    def draw(
        self,
        canvas: Canvas,
        theme: Theme,
        *,
        focused: bool,
        hovered: bool,
        pressed: bool,
    ) -> None:
        r = self.rect
        fill = theme.button
        if self.enabled and pressed:
            fill = theme.pressed
        elif self.enabled and hovered:
            fill = theme.hover
        canvas.rect(r.x, r.y, r.width, r.height, fill)
        if focused and self.enabled:
            canvas.rect(r.x, r.y, r.width, 1, theme.focus)
            canvas.rect(r.x, r.y + r.height - 1, r.width, 1, theme.focus)
            canvas.rect(r.x, r.y, 1, r.height, theme.focus)
            canvas.rect(r.x + r.width - 1, r.y, 1, r.height, theme.focus)
        canvas.text(
            r.x + 4, r.y + 4, self.text, theme.text if self.enabled else theme.disabled
        )


class Column:
    """Vertical panel, focus scope and input router.

    A pointer click must begin and end in the same enabled button. Dragging off
    does not transfer the click to another button. Modal panels consume all
    input, including the frame that closes them. Call reset_input on focus loss
    or scene suspension. UIInput flags must be edge events, not held keys.
    """

    def __init__(
        self,
        children: Iterable[Widget] = (),
        *,
        x: int = 0,
        y: int = 0,
        width: int = 160,
        gap: int = 4,
        padding: int = 4,
        theme: Theme | None = None,
        modal: bool = False,
        on_cancel: Callable[[], None] | None = None,
    ):
        self._validate(width, gap, padding)
        self._x, self._y = x, y
        self._width, self._gap, self._padding = width, gap, padding
        self.theme = theme or Theme()
        self.modal = modal
        self.on_cancel = on_cancel
        self._children: list[Widget] = []
        self._visible: tuple[Widget, ...] = ()
        self._dirty = True
        self._rect = Rect(x, y, width, 0)
        self._capture: Button | None = None
        self._pointer_owned = False
        self._focus: Widget | None = None
        self._hover: Widget | None = None
        self.layout_count = 0
        # Validate the entire group before taking ownership. A failed
        # constructor must not strand widgets in an unreachable panel.
        children = tuple(children)
        if len({id(child) for child in children}) != len(children):
            raise ValueError("a widget cannot appear twice in a panel")
        if any(child._owner is not None for child in children):
            raise ValueError("widget already belongs to a panel")
        for child in children:
            self.add(child)

    @staticmethod
    def _validate(width: int, gap: int, padding: int) -> None:
        if gap < 0 or padding < 0 or width <= 2 * padding:
            raise ValueError(
                "width must exceed padding; gap/padding must be nonnegative"
            )

    @property
    def children(self) -> tuple[Widget, ...]:
        return tuple(self._children)

    @property
    def focused(self) -> Widget | None:
        return self._focus

    @property
    def rect(self) -> Rect:
        self.layout()
        return self._rect

    def configure(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        gap: int | None = None,
        padding: int | None = None,
    ) -> None:
        values = (
            self._x if x is None else x,
            self._y if y is None else y,
            self._width if width is None else width,
            self._gap if gap is None else gap,
            self._padding if padding is None else padding,
        )
        self._validate(*values[2:])
        if values != (self._x, self._y, self._width, self._gap, self._padding):
            self._x, self._y, self._width, self._gap, self._padding = values
            self.invalidate()

    def add(self, child: Widget) -> None:
        if child._owner is not None:
            raise ValueError("widget already belongs to a panel")
        child._owner = self
        self._children.append(child)
        self.invalidate()

    def remove(self, child: Widget) -> None:
        self._children.remove(child)
        child._owner = None
        child.rect = Rect(0, 0, 0, 0)
        if self._capture is child:
            self._capture = None
        if self._focus is child:
            self._focus = None
        if self._hover is child:
            self._hover = None
        self.invalidate()

    def invalidate(self) -> None:
        self._dirty = True

    def layout(self) -> None:
        if not self._dirty:
            return
        self._visible = tuple(child for child in self._children if child.visible)
        y = self._y + self._padding
        for index, child in enumerate(self._visible):
            if index:
                y += self._gap
            child.rect = Rect(
                self._x + self._padding,
                y,
                self._width - 2 * self._padding,
                child.height,
            )
            y += child.height
        self._rect = Rect(self._x, self._y, self._width, y - self._y + self._padding)
        self._dirty = False
        self.layout_count += 1

    def reset_input(self) -> None:
        self._capture = None
        self._pointer_owned = False
        self._hover = None

    def _eligible(self, widget: Widget | None) -> bool:
        return (
            widget is not None
            and widget._owner is self
            and widget.visible
            and widget.enabled
            and widget.focusable
        )

    def _move_focus(self, direction: int) -> bool:
        candidates = [widget for widget in self._visible if self._eligible(widget)]
        if not candidates:
            return False
        if self._focus is None:
            self._focus = candidates[0] if direction > 0 else candidates[-1]
        else:
            index = candidates.index(self._focus)
            self._focus = candidates[(index + direction) % len(candidates)]
        return True

    def _pointer_activation(self, frame: UIInput, consumed: bool) -> Button | None:
        if frame.pointer_pressed:
            self._pointer_owned = consumed
            self._capture = None
            if isinstance(self._hover, Button) and self._eligible(self._hover):
                self._capture = self._hover
                self._focus = self._hover

        if not frame.pointer_released:
            return None
        captured = self._capture
        self._capture = None
        self._pointer_owned = False
        if (
            captured is not None
            and self._eligible(captured)
            and captured.rect.contains(frame.x, frame.y)
        ):
            return captured
        return None

    def update(self, frame: UIInput) -> UIResult:
        self.layout()
        if not self._eligible(self._focus):
            self._focus = None
        if not self._eligible(self._capture):
            self._capture = None
        self._hover = next(
            (
                widget
                for widget in self._visible
                if widget.rect.contains(frame.x, frame.y)
            ),
            None,
        )
        # Snapshot consumption before callbacks can change modal state. Even a
        # removed/disabled button owns its gesture until release, so that release
        # cannot become a game action underneath the panel.
        pointer_consumed = (
            self.modal or self._pointer_owned or self._rect.contains(frame.x, frame.y)
        )
        keyboard_consumed = self.modal
        if frame.reset:
            self.reset_input()
            return UIResult(pointer_consumed, keyboard_consumed)
        if frame.cancel:
            self._capture = None
            self._hover = None
            if frame.pointer_released:
                self._pointer_owned = False
            if self.on_cancel is not None:
                self.on_cancel()
                return UIResult(pointer_consumed, True, True)
            return UIResult(pointer_consumed, keyboard_consumed)

        if frame.next_focus or frame.previous_focus:
            direction = -1 if frame.previous_focus else 1
            if self._move_focus(direction):
                keyboard_consumed = True

        activate = self._pointer_activation(frame, pointer_consumed)
        if frame.confirm and self._eligible(self._focus):
            keyboard_consumed = True
            if activate is None and isinstance(self._focus, Button):
                activate = self._focus
                # Confirm completes this interaction now. Keep pointer ownership
                # to swallow its eventual release, but do not activate twice.
                self._capture = None
        if activate is not None:
            # State is settled before callback; callback may remove the widget,
            # replace the entire panel or request a scene change.
            activate.on_click()
        return UIResult(pointer_consumed, keyboard_consumed)

    def draw(self, canvas: Canvas) -> None:
        self.layout()
        r = self._rect
        canvas.rect(r.x, r.y, r.width, r.height, self.theme.panel)
        for child in self._visible:
            child.draw(
                canvas,
                self.theme,
                focused=child is self._focus,
                hovered=child is self._hover,
                pressed=child is self._capture,
            )
