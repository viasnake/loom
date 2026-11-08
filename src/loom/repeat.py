"""Opt-in logical repeat pulses, separate from physical input edges."""

from collections.abc import Iterable
import math

from .input import InputFrame


def _seconds(value: float, name: str, *, zero: bool = False) -> float:
    try:
        valid = (
            type(value) in (int, float)
            and math.isfinite(value)
            and (value >= 0 if zero else value > 0)
        )
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(
            f"{name} must be finite and {'nonnegative' if zero else 'positive'}"
        )
    return float(value)


class ActionRepeat:
    """Repeat explicitly selected actions; never mutate an InputFrame.

    update returns the initial press and, after delay, at most one pulse per
    action per update. Excess elapsed time is discarded, not queued for bursts.
    A press frame starts the delay without charging its dt. Held-only snapshots
    never start a gesture. reset/cancellation discard gestures until a new press.
    Use one instance per consumer; sharing would advance its clocks twice.
    """

    def __init__(
        self, actions: Iterable[str], *, delay: float = 0.4, interval: float = 0.08
    ):
        if isinstance(actions, (str, bytes)):
            raise TypeError("actions must be a collection of names")
        names = frozenset(actions)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("action names must be nonempty strings")
        self._actions = names
        self._delay = _seconds(delay, "delay")
        self._interval = _seconds(interval, "interval")
        self._remaining: dict[str, float] = {}

    @property
    def actions(self) -> frozenset[str]:
        return self._actions

    def reset(self, actions: Iterable[str] | None = None) -> None:
        """Forget all or selected gestures; held-only snapshots cannot restart."""
        if actions is None:
            self._remaining.clear()
        else:
            if isinstance(actions, (str, bytes)):
                raise TypeError("actions must be a collection of names")
            for name in actions:
                self._remaining.pop(name, None)

    def update(
        self, frame: InputFrame, dt: float, *, reset: bool = False
    ) -> frozenset[str]:
        dt = _seconds(dt, "dt", zero=True)
        if reset or frame.cancelled:
            self.reset()
            return frozenset()
        pulses = set()
        for name in self.actions:
            if name in frame.released:
                self._remaining.pop(name, None)
                # A simultaneous press/release is a completed pulse.
                if name in frame.pressed:
                    pulses.add(name)
            elif name in frame.pressed:
                pulses.add(name)
                if name in frame.held:
                    self._remaining[name] = self._delay
                else:
                    self._remaining.pop(name, None)
            elif name not in frame.held:
                self._remaining.pop(name, None)
            elif name in self._remaining:
                remaining = self._remaining[name] - dt
                if remaining <= 0:
                    pulses.add(name)
                    remaining = self._interval
                self._remaining[name] = remaining
        return frozenset(pulses)
