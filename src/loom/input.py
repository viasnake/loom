"""One input snapshot per update; named actions rather than game key codes."""

from dataclasses import dataclass
from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class InputFrame:
    """One update snapshot. Wheel is the backend delta, positive upward.

    cancelled identifies synthetic releases, which must not commit UI gestures.
    It accompanies released so gameplay can stop held actions normally.
    """

    held: frozenset[str] = frozenset()
    pressed: frozenset[str] = frozenset()
    released: frozenset[str] = frozenset()
    pointer: tuple[float, float] = (0, 0)
    world_pointer: tuple[float, float] | None = None
    wheel: float = 0
    cancelled: frozenset[str] = frozenset()

    def without(self, actions: set[str]) -> "InputFrame":
        return InputFrame(
            self.held - actions,
            self.pressed - actions,
            self.released - actions,
            self.pointer,
            self.world_pointer,
            self.wheel,
            self.cancelled - actions,
        )


class ActionMap:
    """Explicit bindings with atomic, whole-map replacement.

    A physical key may drive several actions. A changed map cancels all previously
    held logical actions once on the next sample. Keys down in that first sample
    are suppressed until observed up, including keys whose binding did not change.
    Replacing with an equivalent normalized map is a no-op. No physical state is
    read during replacement; sample remains the single input polling boundary.
    """

    def __init__(self, bindings: Mapping[str, Iterable[int]]):
        normalized = self._normalize(bindings)
        self._install(normalized)
        self._held: frozenset[str] = frozenset()
        self._resync = False
        self._rebind_pending = False
        self._cancelled: frozenset[str] = frozenset()
        self._blocked_keys: set[int] = set()

    @staticmethod
    def _normalize(bindings: Mapping[str, Iterable[int]]) -> dict[str, tuple[int, ...]]:
        if not isinstance(bindings, Mapping):
            raise TypeError("bindings must be a mapping")
        result = {}
        for name, codes in bindings.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("action names must be nonempty strings")
            if isinstance(codes, (str, bytes, bytearray, Mapping)):
                raise TypeError(
                    f"bindings for {name!r} must be an iterable of key codes, not text or a mapping"
                )
            try:
                codes = tuple(codes)
            except TypeError as error:
                raise TypeError(
                    f"bindings for {name!r} must be iterable key codes"
                ) from error
            if any(type(code) is not int or code < 0 for code in codes):
                raise ValueError(
                    f"bindings for {name!r} must be nonnegative integer key codes"
                )
            result[name] = tuple(sorted(set(codes)))
        return result

    def _install(self, normalized: dict[str, tuple[int, ...]]) -> None:
        self._bindings = MappingProxyType(normalized)
        self._keys = tuple(
            dict.fromkeys(key for codes in normalized.values() for key in codes)
        )

    @property
    def bindings(self) -> Mapping[str, tuple[int, ...]]:
        """Immutable snapshot; old snapshots remain unchanged after replacement."""
        return self._bindings

    def to_data(self) -> dict[str, list[int]]:
        """Independent JSON-safe bindings; pass them to ActionMap to validate/load."""
        return {name: list(codes) for name, codes in self.bindings.items()}

    def replace_bindings(self, bindings: Mapping[str, Iterable[int]]) -> None:
        """Validate completely before changing state; equivalent maps do nothing."""
        normalized = self._normalize(bindings)
        if normalized == self._bindings:
            return
        self._install(normalized)
        self._cancelled |= self._held
        self._held = frozenset()
        self._rebind_pending = True
        self._resync = False

    def sample(
        self,
        is_down: Callable[[int], bool],
        pointer: tuple[float, float] = (0, 0),
        world_pointer: tuple[float, float] | None = None,
        wheel: float = 0,
    ) -> InputFrame:
        # Read each physical key once even when several actions share it.
        keys = {key: bool(is_down(key)) for key in self._keys}
        if self._rebind_pending:
            self._blocked_keys = {key for key, down in keys.items() if down}
            self._rebind_pending = False
        elif self._blocked_keys:
            self._blocked_keys.intersection_update(
                key for key, down in keys.items() if down
            )
        held = frozenset(
            name
            for name, values in self.bindings.items()
            if any(keys[key] and key not in self._blocked_keys for key in values)
        )
        if self._resync:
            self._held = held
            self._resync = False
        frame = InputFrame(
            held,
            held - self._held,
            (self._held - held) | self._cancelled,
            pointer,
            world_pointer,
            wheel,
            self._cancelled,
        )
        self._cancelled = frozenset()
        self._held = held
        return frame

    def reset(self) -> None:
        """Resynchronize without new edges; pending rebind cancellation is retained.

        Rebinding suppression remains in effect until each blocked key is up.
        """
        self._held = frozenset()
        self._resync = True
