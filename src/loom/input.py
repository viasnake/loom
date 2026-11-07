"""One input snapshot per update; named actions rather than game key codes."""

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class InputFrame:
    held: frozenset[str] = frozenset()
    pressed: frozenset[str] = frozenset()
    released: frozenset[str] = frozenset()
    pointer: tuple[float, float] = (0, 0)
    world_pointer: tuple[float, float] | None = None

    def without(self, actions: set[str]) -> "InputFrame":
        return InputFrame(
            self.held - actions,
            self.pressed - actions,
            self.released - actions,
            self.pointer,
            self.world_pointer,
        )


class ActionMap:
    """Explicit key bindings. A key may drive more than one named action."""

    def __init__(self, bindings: Mapping[str, tuple[int, ...]]):
        self.bindings = MappingProxyType(
            {name: tuple(keys) for name, keys in bindings.items()}
        )
        self._keys = tuple(
            dict.fromkeys(key for keys in self.bindings.values() for key in keys)
        )
        self._held: frozenset[str] = frozenset()
        self._resync = False

    def sample(
        self,
        is_down: Callable[[int], bool],
        pointer: tuple[float, float] = (0, 0),
        world_pointer: tuple[float, float] | None = None,
    ) -> InputFrame:
        # Read each physical key once even when several actions share it.
        keys = {key: bool(is_down(key)) for key in self._keys}
        held = frozenset(
            name
            for name, values in self.bindings.items()
            if any(keys[key] for key in values)
        )
        if self._resync:
            self._held = held
            self._resync = False
        frame = InputFrame(
            held, held - self._held, self._held - held, pointer, world_pointer
        )
        self._held = held
        return frame

    def reset(self) -> None:
        """Resynchronize the next sample without synthesizing press/release edges."""
        self._held = frozenset()
        self._resync = True
