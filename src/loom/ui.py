"""Small retained UI with explicit input ownership and invalidation.

Coordinates are already in UI logical pixels. Convert at the display adapter,
not inside widgets. Typography shares font metrics between layout and drawing. This module neither
loads fonts nor changes the global palette.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor, isfinite, nextafter
from typing import Any, Callable, ContextManager, Iterable, Protocol

from .geometry import Rect
from .input import InputFrame
from .text import FontCatalog


class Canvas(Protocol):
    def rect(self, x: int, y: int, w: int, h: int, col: int) -> None: ...
    def text(self, x: int, y: int, s: str, col: int) -> None: ...


class FontCanvas(Canvas, Protocol):
    """Canvas accepting Pyxel's optional font keyword (e.g. Pyxel or Image)."""

    def text(self, x: int, y: int, s: str, col: int, *, font: Any = None) -> None: ...


@dataclass(frozen=True, slots=True)
class Typography:
    """Shared font selection for a panel's measurement and drawing.

    line_height in the catalog must fit the chosen font. No wrapping or clipping
    is implicit; an explicit widget height is respected even if text overflows.
    """

    fonts: FontCatalog
    font: str = "default"

    def measure(self, text: str) -> tuple[int, int]:
        return self.fonts.measure(text, self.font)


class _TextCanvas:
    """Adapt only text; rectangles remain in the same logical coordinates."""

    def __init__(self, canvas: Canvas, typography: Typography):
        self.canvas = canvas
        self.typography = typography

    def rect(self, x: int, y: int, w: int, h: int, col: int) -> None:
        self.canvas.rect(x, y, w, h, col)

    def text(self, x: int, y: int, s: str, col: int) -> None:
        t = self.typography
        t.fonts.draw(self.canvas, x, y, s, col, t.font)


class ClippingCanvas(Canvas, Protocol):
    """Managed clipping with intersection and restoration, including exceptions."""

    def clipped(self, rect: Rect) -> ContextManager[None]: ...


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
    scroll_y: int = 0  # UI pixels; positive moves content upward.
    decrement: bool = False
    increment: bool = False

    @classmethod
    def from_frame(
        cls, frame: InputFrame, *, reset: bool = False, scroll_step: float = 24
    ) -> UIInput:
        """Map standard action edges, using UI rather than world coordinates.

        Physical bindings belong in ActionMap. Held actions never repeat here.
        Consumption remains explicit through UIResult and InputFrame.without.
        Wheel notches (positive up) become rounded logical pixels (positive down).
        """
        if not isfinite(scroll_step) or scroll_step <= 0:
            raise ValueError("scroll_step must be positive and finite")
        return cls(
            x=frame.pointer[0],
            y=frame.pointer[1],
            pointer_pressed="primary" in frame.pressed,
            pointer_released="primary" in frame.released,
            confirm="confirm" in frame.pressed,
            next_focus="next" in frame.pressed,
            previous_focus="previous" in frame.pressed,
            cancel="cancel" in frame.pressed,
            reset=reset,
            scroll_y=round(-frame.wheel * scroll_step),
            decrement="decrement" in frame.pressed,
            increment="increment" in frame.pressed,
        )


@dataclass(frozen=True, slots=True)
class UIResult:
    pointer_consumed: bool = False
    keyboard_consumed: bool = False
    cancelled: bool = False

    @property
    def consumed(self) -> bool:
        return self.pointer_consumed or self.keyboard_consumed


class Widget:
    """A widget belongs to at most one Column; changes invalidate its layout.

    None height asks the widget to size itself. Explicit heights are respected,
    even if text overflows. rect.height is the resolved layout height.
    """

    focusable = False

    def __init__(
        self, *, height: int | None, visible: bool = True, enabled: bool = True
    ):
        if height is not None and height <= 0:
            raise ValueError("height must be positive")
        self._height = height
        self._visible = visible
        self.enabled = enabled
        self.rect = Rect(0, 0, 0, 0)
        self._owner: Column | None = None

    @property
    def height(self) -> int | None:
        return self._height

    @height.setter
    def height(self, value: int | None) -> None:
        if value is not None and value <= 0:
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

    def layout_height(self, typography: Typography | None) -> int:
        return self.height if self.height is not None else 12

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


class _TextWidget(Widget):
    minimum_height = 12
    vertical_padding = 0

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("text must be a string")
        if value != getattr(self, "_text", None):
            self._text = value
            self._invalidate()

    def layout_height(self, typography: Typography | None) -> int:
        self._text_height = (
            typography.measure(self.text)[1]
            if typography is not None
            else len(self.text.split("\n")) * 6
        )
        if self.height is not None:
            return self.height
        return max(self.minimum_height, self._text_height + 2 * self.vertical_padding)


class Label(_TextWidget):
    """Text with automatic line-box height (minimum 12); no wrapping/clipping."""

    def __init__(
        self, text: str, *, height: int | None = None, color: int | None = None
    ):
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


class _Control(_TextWidget):
    """Small interaction hooks; Column owns capture and callback ordering."""

    focusable = True
    draggable = False

    def activate(self) -> None:
        pass

    def adjust(self, direction: int) -> None:
        pass

    def drag(self, x: float | None) -> None:
        pass


class Button(_Control):
    """Text button with automatic height (minimum 20) and centered line boxes.

    Text has 4-pixel horizontal padding. Auto height leaves at least 4 pixels
    above and below; explicit undersized heights draw text from the top.
    """

    focusable = True
    minimum_height = 20
    vertical_padding = 4

    def __init__(
        self,
        text: str,
        on_click: Callable[[], None],
        *,
        height: int | None = None,
        enabled: bool = True,
    ):
        super().__init__(height=height, enabled=enabled)
        self.text = text
        self.on_click = on_click

    def activate(self) -> None:
        self.on_click()

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
        self._draw_label(canvas, theme)

    def _draw_label(self, canvas: Canvas, theme: Theme) -> None:
        r = self.rect
        canvas.text(
            r.x + 4,
            r.y + max(0, (r.height - getattr(self, "_text_height", 6)) // 2),
            self.text,
            theme.text if self.enabled else theme.disabled,
        )


class Toggle(Button):
    """Boolean setting; click release or confirm toggles once.

    Assigning checked notifies on_change only when the value changes. Initial
    construction is silent. Text width must leave room for the 18-pixel marker.
    """

    def __init__(
        self,
        text: str,
        checked: bool = False,
        on_change: Callable[[bool], None] | None = None,
        *,
        height: int | None = None,
        enabled: bool = True,
    ):
        if type(checked) is not bool:
            raise TypeError("checked must be a bool")
        self._checked = checked
        self.on_change = on_change
        super().__init__(text, self._toggle, height=height, enabled=enabled)

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        if type(value) is not bool:
            raise TypeError("checked must be a bool")
        if value != self._checked:
            self._checked = value
            if self.on_change is not None:
                self.on_change(value)

    def _toggle(self) -> None:
        self.checked = not self.checked

    def _draw_label(self, canvas: Canvas, theme: Theme) -> None:
        r = self.rect
        color = theme.text if self.enabled else theme.disabled
        y = r.y + max(0, (r.height - 10) // 2)
        canvas.rect(r.x + 4, y, 12, 10, color)
        canvas.rect(r.x + 5, y + 1, 10, 8, theme.panel)
        if self.checked:
            canvas.rect(r.x + 7, y + 3, 6, 4, theme.focus if self.enabled else color)
        canvas.text(
            r.x + 22,
            r.y + max(0, (r.height - getattr(self, "_text_height", 6)) // 2),
            self.text,
            color,
        )


class Slider(_Control):
    """Stepped numeric setting with immediate, change-only notifications.

    Values snap to minimum + n * step; maximum is also a reachable endpoint.
    Half-step ties round upward, allowing one quotient ULP for float arithmetic.
    Press anywhere in the control (including its label) to set the value from
    the horizontal track position. Drag captures until release and clamps
    outside the track. Confirm alone makes no change. Cancel/reset stop
    editing without rolling back changes. Assigning value uses the same snapping
    and notification rules. Steps must be representable throughout the range;
    ranges with more than 2**52 intervals are rejected. Explicit heights may
    overflow, as with other widgets.
    """

    draggable = True
    minimum_height = 28
    vertical_padding = 11

    def __init__(
        self,
        text: str,
        value: float = 0,
        *,
        minimum: float = 0,
        maximum: float = 1,
        step: float = 0.1,
        on_change: Callable[[float], None] | None = None,
        height: int | None = None,
        enabled: bool = True,
    ):
        for name, number in (
            ("minimum", minimum),
            ("maximum", maximum),
            ("step", step),
        ):
            self._validate_number(name, number)
        if maximum <= minimum or step <= 0:
            raise ValueError("maximum must exceed minimum and step must be positive")
        if not isfinite(maximum - minimum) or not isfinite((maximum - minimum) / step):
            raise ValueError("range and step ratio must be finite")
        if (
            minimum + step == minimum
            or maximum - step == maximum
            or (maximum - minimum) / step > 2**52
        ):
            raise ValueError("step is too small to represent throughout this range")
        self._minimum, self._maximum, self._step = (
            float(minimum),
            float(maximum),
            float(step),
        )
        self._value = self._normalize(value)
        self.on_change = on_change
        super().__init__(height=height, enabled=enabled)
        self.text = text

    @staticmethod
    def _validate_number(name: str, value: float) -> None:
        try:
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and isfinite(value)
            )
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"{name} must be a finite number")

    @property
    def minimum(self) -> float:
        return self._minimum

    @property
    def maximum(self) -> float:
        return self._maximum

    @property
    def step(self) -> float:
        return self._step

    def _normalize(self, value: float) -> float:
        self._validate_number("value", value)
        value = min(self.maximum, max(self.minimum, value))
        if value == self.maximum:
            return self.maximum
        ratio = (value - self.minimum) / self.step
        index = floor(ratio)
        # One quotient ULP accounts for decimal half-steps such as .15 / .1.
        if nextafter(ratio, float("inf")) >= index + 0.5:
            index += 1
        return min(self.maximum, max(self.minimum, self.minimum + index * self.step))

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        value = self._normalize(value)
        if value != self._value:
            self._value = value
            if self.on_change is not None:
                self.on_change(value)

    def adjust(self, direction: int) -> None:
        index = (self.value - self.minimum) / self.step
        # One quotient ULP prevents a rounded lattice value skipping a step.
        index = (
            floor(nextafter(index, float("inf"))) + 1
            if direction > 0
            else ceil(nextafter(index, float("-inf"))) - 1
        )
        self.value = min(
            self.maximum, max(self.minimum, self.minimum + index * self.step)
        )

    def drag(self, x: float | None) -> None:
        if x is None or not isfinite(x):
            return
        start, width = self._track()
        fraction = min(1.0, max(0.0, (x - start) / width))
        self.value = self.minimum + fraction * (self.maximum - self.minimum)

    def _track(self) -> tuple[int, int]:
        return self.rect.x + 5, max(1, self.rect.width - 11)

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
        color = theme.text if self.enabled else theme.disabled
        fill = theme.button
        if self.enabled and pressed:
            fill = theme.pressed
        elif self.enabled and hovered:
            fill = theme.hover
        canvas.rect(r.x, r.y, r.width, r.height, fill)
        if focused and self.enabled:
            canvas.rect(r.x, r.y, r.width, 1, theme.focus)
            canvas.rect(r.x, r.y + r.height - 1, r.width, 1, theme.focus)
        canvas.text(r.x + 4, r.y + 4, self.text, color)
        start, width = self._track()
        y = r.y + getattr(self, "_text_height", 6) + 11
        canvas.rect(start, y, width + 1, 2, theme.disabled)
        fraction = (self.value - self.minimum) / (self.maximum - self.minimum)
        knob = start + round(fraction * width)
        canvas.rect(
            start, y, knob - start, 2, theme.focus if self.enabled else theme.disabled
        )
        canvas.rect(knob - 2, y - 3, 5, 8, color)


class Column:
    """Vertical panel, focus scope and input router.

    A pointer click must begin and end in the same enabled button. Dragging off
    does not transfer the click to another button. Modal panels consume all
    input, including the frame that closes them. Call reset_input on focus loss
    or scene suspension. UIInput flags must be edge events, not held keys.

    With typography, the drawing target must accept Pyxel's text(..., font=)
    keyword. Fonts are measured before input routing; changing registrations or
    assigning typography invalidates layout automatically. Text is not wrapped
    or clipped to individual widgets; choose sufficient width/explicit heights.

    viewport_height fixes the outer panel height at construction. Its padded
    interior clips children. scroll_offset uses logical pixels and clamps to the
    content range; positive UIInput.scroll_y scrolls down while over the panel.
    Tab and confirm reveal focus (oversized widgets align at the top). Scrolling
    cancels a pending click but retains ownership until pointer release.
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
        typography: Typography | None = None,
        viewport_height: int | None = None,
        modal: bool = False,
        on_cancel: Callable[[], None] | None = None,
    ):
        self._validate(width, gap, padding)
        self._x, self._y = x, y
        self._width, self._gap, self._padding = width, gap, padding
        if viewport_height is not None and type(viewport_height) is not int:
            raise TypeError("viewport_height must be an integer or None")
        if viewport_height is not None and viewport_height <= 2 * padding:
            raise ValueError("viewport_height must exceed twice the padding")
        self._viewport_height = viewport_height
        self._scroll_offset = 0
        self._content_height = 0
        self.theme = theme or Theme()
        self.typography = typography
        self._font_state: tuple[Typography | None, int] | None = None
        self.modal = modal
        self.on_cancel = on_cancel
        self._children: list[Widget] = []
        self._visible: tuple[Widget, ...] = ()
        self._dirty = True
        self._rect = Rect(x, y, width, 0)
        self._capture: _Control | None = None
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
    def viewport_height(self) -> int | None:
        return self._viewport_height

    @property
    def scroll_offset(self) -> int:
        self.layout()
        return self._scroll_offset

    @scroll_offset.setter
    def scroll_offset(self, value: int) -> None:
        if type(value) is not int:
            raise TypeError("scroll_offset must be an integer")
        self.layout()
        limit = max(0, self._content_height - self._rect.height)
        value = min(max(0, value), limit)
        delta = self._scroll_offset - value
        if delta:
            self._scroll_offset = value
            for child in self._visible:
                r = child.rect
                child.rect = Rect(r.x, r.y + delta, r.width, r.height)
            # Scrolling must not change the target of an in-flight click.
            self._capture = None
            self._hover = None

    def _content_rect(self) -> Rect:
        r, p = self._rect, self._padding
        return Rect(r.x + p, r.y + p, r.width - 2 * p, max(0, r.height - 2 * p))

    def _ensure_focus_visible(self) -> None:
        if self._focus is None or self.viewport_height is None:
            return
        view, focused = self._content_rect(), self._focus.rect
        if focused.y < view.y or focused.height > view.height:
            self.scroll_offset += focused.y - view.y
        elif focused.y + focused.height > view.y + view.height:
            self.scroll_offset += focused.y + focused.height - view.y - view.height

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
        if self.viewport_height is not None and self.viewport_height <= 2 * values[4]:
            raise ValueError("viewport_height must exceed twice the padding")
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
        font_state = (
            self.typography,
            self.typography.fonts.revision if self.typography is not None else 0,
        )
        if font_state != self._font_state:
            self._dirty = True
        if not self._dirty:
            return
        self._visible = tuple(child for child in self._children if child.visible)
        y = self._y + self._padding
        for index, child in enumerate(self._visible):
            if index:
                y += self._gap
            height = child.layout_height(self.typography)
            child.rect = Rect(
                self._x + self._padding,
                y,
                self._width - 2 * self._padding,
                height,
            )
            y += height
        self._content_height = y - self._y + self._padding
        height = (
            self.viewport_height
            if self.viewport_height is not None
            else self._content_height
        )
        self._rect = Rect(self._x, self._y, self._width, height)
        self._scroll_offset = min(
            self._scroll_offset, max(0, self._content_height - height)
        )
        if self._scroll_offset:
            for child in self._visible:
                r = child.rect
                child.rect = Rect(r.x, r.y - self._scroll_offset, r.width, r.height)
        self._dirty = False
        self._font_state = font_state
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
        self._ensure_focus_visible()
        return True

    def _pointer_action(
        self, frame: UIInput, consumed: bool
    ) -> Callable[[], None] | None:
        if frame.pointer_pressed:
            self._pointer_owned = consumed
            self._capture = None
            if isinstance(self._hover, _Control) and self._eligible(self._hover):
                self._capture = self._hover
                self._focus = self._hover
        captured = self._capture
        if frame.pointer_released:
            self._capture = None
            self._pointer_owned = False
        if captured is None or not self._eligible(captured):
            return None
        if captured.draggable:
            return lambda: captured.drag(frame.x)
        if (
            frame.pointer_released
            and self._content_rect().contains(frame.x, frame.y)
            and captured.rect.contains(frame.x, frame.y)
        ):
            return captured.activate
        return None

    def update(self, frame: UIInput) -> UIResult:
        self.layout()
        if not self._eligible(self._focus):
            self._focus = None
        if not self._eligible(self._capture):
            self._capture = None
        view = self._content_rect()
        self._hover = next(
            (
                widget
                for widget in self._visible
                if view.contains(frame.x, frame.y)
                and widget.rect.contains(frame.x, frame.y)
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

        if (
            frame.scroll_y
            and self.viewport_height is not None
            and self._rect.contains(frame.x, frame.y)
        ):
            self.scroll_offset += frame.scroll_y

        if frame.next_focus or frame.previous_focus:
            direction = -1 if frame.previous_focus else 1
            if self._move_focus(direction):
                keyboard_consumed = True

        action = self._pointer_action(frame, pointer_consumed)
        if isinstance(self._focus, _Control) and self._eligible(self._focus):
            if frame.confirm:
                self._ensure_focus_visible()
                keyboard_consumed = True
                if action is None and not self._focus.draggable:
                    action = self._focus.activate
                self._capture = None
            if (frame.decrement or frame.increment) and self._focus.draggable:
                self._ensure_focus_visible()
                keyboard_consumed = True
                if action is None and frame.decrement != frame.increment:
                    control = self._focus
                    direction = 1 if frame.increment else -1
                    action = lambda: control.adjust(direction)
                    self._capture = None
        if action is not None:
            # Settle ownership before callback, which may remove this control.
            action()
        return UIResult(pointer_consumed, keyboard_consumed)

    def draw(self, canvas: Canvas | FontCanvas | ClippingCanvas) -> None:
        """Draw a panel; finite viewports require managed ``clipped(Rect)``.

        Use PyxelCanvas for finite panels, not raw Pyxel.clip (which cannot read
        back its prior state). Typography additionally requires text(..., font=).
        Unbounded panels retain compatibility with four-argument Canvas.text.
        """
        self.layout()
        if self.viewport_height is not None and not callable(
            getattr(canvas, "clipped", None)
        ):
            raise TypeError("finite Column requires a ClippingCanvas; use PyxelCanvas")
        r = self._rect
        canvas.rect(r.x, r.y, r.width, r.height, self.theme.panel)
        if self.viewport_height is None:
            self._draw_children(canvas)
        else:
            with canvas.clipped(self._content_rect()):
                self._draw_children(canvas)

    def _draw_children(self, canvas: Canvas) -> None:
        if self.typography is not None:
            canvas = _TextCanvas(canvas, self.typography)
        view = self._content_rect()
        for child in self._visible:
            if self.viewport_height is not None and (
                child.rect.y + child.rect.height <= view.y
                or child.rect.y >= view.y + view.height
            ):
                continue
            child.draw(
                canvas,
                self.theme,
                focused=child is self._focus,
                hovered=child is self._hover,
                pressed=child is self._capture,
            )
