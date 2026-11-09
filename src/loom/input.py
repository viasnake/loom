"""One input snapshot per update; named actions rather than game key codes."""

from dataclasses import dataclass, field
from collections.abc import Callable, Iterable, Mapping
from types import MappingProxyType
from math import hypot

from .sticks import StickBinding

_EMPTY_STICKS = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class InputFrame:
    """One update snapshot. Wheel is the backend delta, positive upward.

    Action collections and pointer coordinates are copied into immutable values;
    callers can reuse their mutable input buffers after constructing a frame.

    cancelled identifies interrupted digital actions and nonneutral sticks.
    Digital cancellations also appear in released; stick names do not generate
    held/pressed/released edges. sticks contains normalized vectors, never raw axes.
    GameApp sets world_pointer to a discrete rendered source pixel, or None.
    """

    held: frozenset[str] = frozenset()
    pressed: frozenset[str] = frozenset()
    released: frozenset[str] = frozenset()
    pointer: tuple[float, float] = (0, 0)
    world_pointer: tuple[float, float] | None = None
    wheel: float = 0
    cancelled: frozenset[str] = frozenset()
    sticks: Mapping[str, tuple[float, float]] = field(
        default_factory=lambda: _EMPTY_STICKS, hash=False
    )

    def __post_init__(self):
        for name in ("held", "pressed", "released", "cancelled"):
            value = getattr(self, name)
            if not isinstance(value, frozenset):
                if isinstance(value, (str, bytes, bytearray, Mapping)):
                    raise TypeError(f"{name} must be a collection of action names")
                object.__setattr__(self, name, frozenset(value))
        for name in ("pointer", "world_pointer"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        if not isinstance(self.sticks, Mapping):
            raise TypeError("sticks must be a mapping")
        if not self.sticks:
            object.__setattr__(self, "sticks", _EMPTY_STICKS)
            return
        snapshot = {}
        for name, vector in self.sticks.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("stick names must be nonempty strings")
            vector = tuple(vector)
            if len(vector) != 2 or any(
                type(v) not in (int, float) or not -1 <= v <= 1 for v in vector
            ):
                raise ValueError(
                    "stick vectors must contain two finite normalized components"
                )
            if hypot(*vector) > 1 + 1e-12:
                raise ValueError("stick vector magnitude must not exceed one")
            snapshot[name] = vector
        object.__setattr__(self, "sticks", MappingProxyType(snapshot))

    def without(self, actions: set[str]) -> "InputFrame":
        return InputFrame(
            self.held - actions,
            self.pressed - actions,
            self.released - actions,
            self.pointer,
            self.world_pointer,
            self.wheel,
            self.cancelled - actions,
            {name: value for name, value in self.sticks.items() if name not in actions},
        )


class ActionMap:
    """Explicit bindings with atomic, whole-map replacement.

    A physical key may drive several actions. A changed map cancels all previously
    held logical actions once on the next sample. Keys down in that first sample
    are suppressed until observed up, including keys whose binding did not change.
    Replacing with an equivalent normalized map is a no-op. No physical state is
    read during replacement; sample remains the single input polling boundary.
    """

    def __init__(
        self,
        bindings: Mapping[str, Iterable[int]],
        *,
        watched_keys: Iterable[int] = (),
        sticks: Mapping[str, StickBinding] | None = None,
    ):
        if sticks is not None and not isinstance(sticks, Mapping):
            raise TypeError("sticks must be a mapping")
        self._sticks = MappingProxyType(dict(sticks) if sticks is not None else {})
        for name, binding in self._sticks.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("stick names must be nonempty strings")
            if not isinstance(binding, StickBinding):
                raise TypeError("stick bindings must be StickBinding instances")
        self._axis_keys = tuple(
            dict.fromkeys(
                code
                for binding in self._sticks.values()
                for code in (binding.x, binding.y)
            )
        )
        self._stick_values: dict[str, tuple[float, float]] = {}
        self._blocked_sticks: set[str] = set()
        self._watched_keys = self._normalize({"watched": watched_keys})["watched"]
        self._physical_held: frozenset[int] = frozenset()
        self._physical_pressed: frozenset[int] = frozenset()
        normalized = self._normalize(bindings)
        self._install(normalized)
        self._held: frozenset[str] = frozenset()
        self._resync = False
        self._rebind_pending = False
        self._cancel_raw_pending = False
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
        if normalized.keys() & self._sticks.keys():
            raise ValueError("digital action and stick names must be distinct")
        digital_codes = {key for codes in normalized.values() for key in codes} | set(
            self._watched_keys
        )
        if digital_codes.intersection(self._axis_keys):
            raise ValueError(
                "stick axis codes must not be polled as digital or watched keys"
            )
        self._bindings = MappingProxyType(normalized)
        self._keys = tuple(
            dict.fromkeys(
                [key for codes in normalized.values() for key in codes]
                + list(self._watched_keys)
            )
        )

    @property
    def bindings(self) -> Mapping[str, tuple[int, ...]]:
        """Immutable snapshot; old snapshots remain unchanged after replacement."""
        return self._bindings

    @property
    def sticks(self) -> Mapping[str, StickBinding]:
        """Fixed, immutable stick configuration; independent of digital rebinding."""
        return self._sticks

    @property
    def physical_held(self) -> frozenset[int]:
        """Last raw snapshot of bound and watched keys, before action filtering.

        For settings capture, not routed gameplay. Read only after sample().
        """
        return self._physical_held

    @property
    def physical_pressed(self) -> frozenset[int]:
        """Raw edges from the last sample; reset suppresses these edges too."""
        return self._physical_pressed

    def to_data(self) -> dict[str, list[int]]:
        """Independent JSON-safe bindings; pass them to ActionMap to validate/load."""
        return {name: list(codes) for name, codes in self.bindings.items()}

    def replace_bindings(self, bindings: Mapping[str, Iterable[int]]) -> None:
        """Validate completely before changing state; equivalent maps do nothing."""
        normalized = self._normalize(bindings)
        if normalized == self._bindings:
            return
        self._install(normalized)
        self._cancel_actions()

    def _cancel_actions(self) -> None:
        self._cancelled |= self._held | {
            name for name, value in self._stick_values.items() if value != (0, 0)
        }
        self._stick_values = {}
        self._held = frozenset()
        self._rebind_pending = True
        self._resync = False

    def cancel(self) -> None:
        """Queue an explicit input interruption for the next sample.

        Emit cancelled/released for prior digital held actions once, and suppress
        all keys down at that next sample until up. Nonneutral sticks are reported
        in cancelled only and suppressed until radial neutral. Also suppress that sample's
        physical_pressed and wheel; pointer and physical_held stay raw. Cancel an active KeyCapture
        separately because it consumes raw held snapshots. This is not automatic
        OS-focus detection. Repeated requests before sampling coalesce.
        """
        self._cancel_actions()
        self._cancel_raw_pending = True

    def sample(
        self,
        is_down: Callable[[int], bool],
        pointer: tuple[float, float] = (0, 0),
        world_pointer: tuple[float, float] | None = None,
        wheel: float = 0,
        *,
        axis_value: Callable[[int], int] | None = None,
    ) -> InputFrame:
        if self._axis_keys and axis_value is None:
            raise ValueError("stick bindings require an axis_value reader")
        axes = {key: axis_value(key) for key in self._axis_keys}
        raw_sticks = {
            name: binding.normalize(axes[binding.x], axes[binding.y])
            for name, binding in self._sticks.items()
        }
        nonneutral = {name for name, value in raw_sticks.items() if value != (0, 0)}
        # Digital and analog codes are polled separately, once per unique code.
        keys = {key: bool(is_down(key)) for key in self._keys}
        physical = frozenset(key for key, down in keys.items() if down)
        cancelling = self._cancel_raw_pending
        self._physical_pressed = (
            frozenset()
            if self._resync or self._cancel_raw_pending
            else physical - self._physical_held
        )
        self._cancel_raw_pending = False
        self._physical_held = physical
        if self._rebind_pending:
            self._blocked_sticks = nonneutral
            self._blocked_keys = {key for key, down in keys.items() if down}
            self._rebind_pending = False
        elif self._blocked_keys:
            self._blocked_keys.intersection_update(
                key for key, down in keys.items() if down
            )
        self._blocked_sticks.intersection_update(nonneutral)
        stick_values = {
            name: (0.0, 0.0) if name in self._blocked_sticks else value
            for name, value in raw_sticks.items()
        }
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
            (self._held - held) | (self._cancelled - self._sticks.keys()),
            pointer,
            world_pointer,
            0 if cancelling else wheel,
            self._cancelled,
            stick_values,
        )
        self._cancelled = frozenset()
        self._held = held
        self._stick_values = stick_values
        return frame

    def reset(self) -> None:
        """Resynchronize without new edges; pending rebind cancellation is retained.

        Rebinding suppression remains in effect until each blocked key is up.
        """
        # Keep the previous logical snapshot until sample so reset→cancel can
        # still notify its consumers. Resync itself continues to emit no edges.
        self._resync = True
