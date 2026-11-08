"""Top-level panel routing and gesture ownership, without a UI tree."""

from dataclasses import dataclass, replace
from typing import Iterable

from .input import InputFrame
from .ui import Column, UIInput


@dataclass(frozen=True, slots=True)
class UIRouteResult:
    remaining: InputFrame
    pointer_consumed: bool = False
    keyboard_consumed: bool = False


class UIRouter:
    """Panels are ordered back to front; one panel owns keyboard focus.

    Register additional game aliases in pointer_actions/navigation_actions;
    built-in UI action names are always included.
    physical bindings are never inferred. Groups must be disjoint. Consumed
    actions remain blocked until release; game-owned gestures keep their release
    even over UI. Modal entry and reset explicitly cancel game-held actions once,
    then block those still physically held until release. reset should accompany
    focus loss/resynchronization, not replace a real release event every frame.

    InputFrame is a sampled state: simultaneous press/release of the same action
    is treated as a completed pulse, not two distinct gestures. Pointer coordinates
    remain in remaining; coordinate-driven gameplay must check pointer_consumed.
    """

    def __init__(
        self,
        panels: Iterable[Column] = (),
        *,
        pointer_actions: Iterable[str] = (),
        navigation_actions: Iterable[str] = (),
    ):
        if isinstance(pointer_actions, (str, bytes)) or isinstance(
            navigation_actions, (str, bytes)
        ):
            raise TypeError("action aliases must be a collection, not a string")
        self.pointer_actions = frozenset(pointer_actions) | {"primary"}
        self.navigation_actions = frozenset(navigation_actions) | {
            "confirm",
            "cancel",
            "next",
            "previous",
        }
        if self.pointer_actions & self.navigation_actions:
            raise ValueError("pointer and navigation action groups must be disjoint")
        if any(
            not isinstance(name, str) or not name.strip()
            for name in self.pointer_actions | self.navigation_actions
        ):
            raise ValueError("action names must be nonempty strings")
        self._panels: list[Column] = []
        self._active: Column | None = None
        self._pointer_owner: Column | None = None
        self._pointer_owned = False
        self._blocked: set[str] = set()
        self._game_held: set[str] = set()
        for panel in panels:
            self.add(panel)

    @property
    def panels(self) -> tuple[Column, ...]:
        return tuple(self._panels)

    @property
    def active(self) -> Column | None:
        return self._active

    def add(self, panel: Column) -> None:
        if panel in self._panels:
            raise ValueError("panel is already routed")
        self._panels.append(panel)

    def remove(self, panel: Column) -> None:
        self._panels.remove(panel)
        panel.reset_input()
        if self._active is panel:
            self._active = None
        if self._pointer_owner is panel:
            self._pointer_owner = None  # Keep ownership until release.

    def bring_to_front(self, panel: Column) -> None:
        self._panels.remove(panel)
        self._panels.append(panel)

    def _modal(self) -> Column | None:
        return next((p for p in reversed(self._panels) if p.modal), None)

    def update(
        self, frame: InputFrame, *, reset: bool = False, scroll_step: float = 24
    ) -> UIRouteResult:
        ui = UIInput.from_frame(frame, reset=reset, scroll_step=scroll_step)
        snapshot = self.panels
        modal = self._modal()
        eligible = snapshot[snapshot.index(modal) :] if modal is not None else snapshot
        if reset or (
            self._pointer_owner is not None and self._pointer_owner not in eligible
        ):
            if self._pointer_owner is not None:
                self._pointer_owner.reset_input()
            self._pointer_owner = None
        if reset:
            self._pointer_owned = False
        if self._active not in eligible:
            self._active = eligible[-1] if eligible else None
        hit = next((p for p in reversed(eligible) if p.rect.contains(ui.x, ui.y)), None)
        pointer = self._pointer_owner if self._pointer_owned else hit
        if ui.pointer_pressed and not self._pointer_owned:
            pointer = hit
            if pointer is not None:
                self._pointer_owner = pointer
                self._pointer_owned = True
                self._active = pointer
        game_pointer_owned = bool(self._game_held & self.pointer_actions)
        pointer_consumed = self._pointer_owned or (
            hit is not None and not game_pointer_owned
        )
        keyboard_consumed = False
        for panel in snapshot:
            if panel not in self._panels:
                continue
            owns_pointer = panel is pointer and panel in eligible
            owns_keyboard = panel is self._active and panel in eligible
            routed = replace(
                ui,
                x=ui.x if owns_pointer or panel is hit else None,
                y=ui.y if owns_pointer or panel is hit else None,
                pointer_pressed=ui.pointer_pressed and owns_pointer,
                pointer_released=ui.pointer_released and owns_pointer,
                scroll_y=ui.scroll_y if panel is hit else 0,
                confirm=ui.confirm and owns_keyboard,
                cancel=ui.cancel and owns_keyboard,
                next_focus=ui.next_focus and owns_keyboard,
                previous_focus=ui.previous_focus and owns_keyboard,
            )
            result = panel.update(routed)
            if owns_keyboard:
                keyboard_consumed |= result.keyboard_consumed
        if ui.pointer_released:
            self._pointer_owned = False
            self._pointer_owner = None
        interrupted = reset or modal is not None or self._modal() is not None
        if interrupted:
            pointer_consumed = keyboard_consumed = True
            cancelled = frozenset(self._game_held)
            self._blocked.update(frame.held | frame.pressed)
            remaining = InputFrame(
                released=cancelled,
                pointer=frame.pointer,
                world_pointer=frame.world_pointer,
            )
        else:
            candidates: set[str] = set()
            if pointer_consumed:
                candidates.update(self.pointer_actions)
            if keyboard_consumed:
                candidates.update(self.navigation_actions)
            # Hover never steals a gesture that gameplay already received.
            candidates.difference_update(self._game_held)
            self._blocked.update(candidates & (frame.pressed | frame.held))
            remaining = InputFrame(
                frame.held - self._blocked,
                frame.pressed - self._blocked,
                frame.released - self._blocked,
                frame.pointer,
                frame.world_pointer,
                0 if hit is not None else frame.wheel,
            )
        self._blocked.difference_update(frame.released)
        # Resynchronization can report an up snapshot without a release edge.
        self._blocked.intersection_update(frame.held)
        if "primary" not in frame.held:
            if self._pointer_owner is not None:
                self._pointer_owner.reset_input()
            self._pointer_owned = False
            self._pointer_owner = None
        self._game_held = set(remaining.held)
        return UIRouteResult(remaining, pointer_consumed, keyboard_consumed)

    def draw(self, canvas) -> None:
        for panel in self.panels:
            if panel in self._panels:
                panel.draw(canvas)
