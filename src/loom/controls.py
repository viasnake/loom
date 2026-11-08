"""Binding drafts and key capture; no UI, device names or persistence policy."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from .input import ActionMap


class BindingEditor:
    """Edit a validated draft without changing live ActionMap bindings.

    Defaults define the known actions. Loaded bindings must contain exactly those
    actions; applications must migrate saved schemas explicitly. Reassign removes
    conflicting keys from other actions and may leave them unbound. The game must
    protect essential controls or provide restore/cancel UI before applying.
    """

    def __init__(
        self,
        defaults: Mapping[str, Iterable[int]],
        bindings: Mapping[str, Iterable[int]] | None = None,
    ):
        self._defaults = ActionMap(defaults).bindings
        current = self._defaults if bindings is None else ActionMap(bindings).bindings
        if current.keys() != self._defaults.keys():
            raise ValueError("bindings must contain exactly the default action names")
        self._bindings = current

    @property
    def defaults(self) -> Mapping[str, tuple[int, ...]]:
        return self._defaults

    @property
    def bindings(self) -> Mapping[str, tuple[int, ...]]:
        return self._bindings

    def _keys(self, action: str, keys: Iterable[int]) -> tuple[int, ...]:
        if action not in self._defaults:
            raise KeyError(action)
        return ActionMap({action: keys}).bindings[action]

    def conflicts(self, action: str, keys: Iterable[int]) -> dict[str, tuple[int, ...]]:
        """Return other actions sharing the proposed keys; never mutate the draft."""
        requested = set(self._keys(action, keys))
        return {
            name: tuple(code for code in bound if code in requested)
            for name, bound in self._bindings.items()
            if name != action and requested.intersection(bound)
        }

    def assign(
        self,
        action: str,
        keys: Iterable[int],
        *,
        conflict: Literal["reject", "share", "reassign"] = "reject",
    ) -> None:
        """Replace one action's keys atomically using an explicit conflict policy."""
        if conflict not in ("reject", "share", "reassign"):
            raise ValueError("conflict must be reject, share or reassign")
        keys = self._keys(action, keys)
        conflicts = self.conflicts(action, keys)
        if conflicts and conflict == "reject":
            raise ValueError(f"keys conflict with actions: {', '.join(conflicts)}")
        updated = dict(self._bindings)
        if conflict == "reassign":
            requested = set(keys)
            for name in conflicts:
                updated[name] = tuple(
                    key for key in updated[name] if key not in requested
                )
        updated[action] = keys
        self._bindings = MappingProxyType(updated)

    def clear(self, action: str) -> None:
        """Unbind an action. Essential-action protection belongs to the game."""
        self.assign(action, ())

    def restore_defaults(self) -> None:
        self._bindings = self._defaults

    def to_data(self) -> dict[str, list[int]]:
        return {action: list(keys) for action, keys in self._bindings.items()}


@dataclass(frozen=True, slots=True)
class CaptureResult:
    action: str | None = None
    status: Literal["idle", "waiting", "captured", "ambiguous", "cancelled"] = "idle"
    key: int | None = None
    candidates: tuple[int, ...] = ()


class KeyCapture:
    """Capture one fresh key from caller-supplied physical-down snapshots.

    Use ActionMap.physical_held with a finite watched_keys set; do not poll again.
    begin ignores keys already down until released and pressed again. Multiple
    fresh keys are ambiguous: nothing is selected, and all keys must be released
    before retrying. Success/cancellation is terminal until begin is called again.
    Escape is not special: the game decides which UI/action cancels capture.
    """

    def __init__(self):
        self._result = CaptureResult()
        self._previous: frozenset[int] = frozenset()
        self._wait_for_up = False

    @property
    def result(self) -> CaptureResult:
        return self._result

    @staticmethod
    def _snapshot(held: Iterable[int]) -> frozenset[int]:
        if isinstance(held, (str, bytes, bytearray, Mapping)):
            raise TypeError("held must be an iterable of integer key codes")
        codes = tuple(held)
        if any(type(code) is not int or code < 0 for code in codes):
            raise ValueError("held key codes must be nonnegative integers")
        return frozenset(codes)

    def begin(self, action: str, held: Iterable[int] = ()) -> None:
        if not isinstance(action, str) or not action.strip():
            raise ValueError("action must be a nonempty string")
        snapshot = self._snapshot(held)
        self._previous = snapshot
        self._wait_for_up = False
        self._result = CaptureResult(action, "waiting")

    def update(self, held: Iterable[int]) -> CaptureResult:
        if self._result.status not in ("waiting", "ambiguous"):
            return self._result
        snapshot = self._snapshot(held)
        fresh = snapshot - self._previous
        self._previous = snapshot
        action = self._result.action
        if self._wait_for_up:
            if not snapshot:
                self._wait_for_up = False
                self._result = CaptureResult(action, "waiting")
        elif len(fresh) == 1:
            self._result = CaptureResult(action, "captured", next(iter(fresh)))
        elif len(fresh) > 1:
            self._wait_for_up = True
            self._result = CaptureResult(
                action, "ambiguous", candidates=tuple(sorted(fresh))
            )
        return self._result

    def cancel(self) -> CaptureResult:
        if self._result.status in ("waiting", "ambiguous"):
            self._result = CaptureResult(self._result.action, "cancelled")
        return self._result
