"""Deterministic, manually advanced timers and numeric interpolation."""

from collections.abc import Callable
from math import isfinite


def linear(t: float) -> float:
    return t


def smoothstep(t: float) -> float:
    return t * t * (3 - 2 * t)


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def _finite(name: str, value: float) -> float:
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
    return float(value)


class _Task:
    def __init__(self):
        self._done = False
        self._cancelled = False

    @property
    def done(self) -> bool:
        """True for either completion or cancellation."""
        return self._done

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        """Cancel without notification; cancelling a completed task does nothing."""
        if not self._done:
            self._done = self._cancelled = True
            self._dispose()

    def _dispose(self) -> None:
        """Release user callables while allowing completed handles to be retained."""
        pass

    def _advance(self, dt: float) -> Callable[[], None] | None:
        raise NotImplementedError


class Tween(_Task):
    """A numeric value owned by a Timeline. Cancellation keeps the latest value."""

    def __init__(
        self,
        start: float,
        end: float,
        duration: float,
        *,
        ease: Callable[[float], float] = linear,
        on_complete: Callable[[], None] | None = None,
    ):
        super().__init__()
        self._start = _finite("start", start)
        self._end = _finite("end", end)
        self._duration = _finite("duration", duration)
        if self._duration <= 0:
            raise ValueError("duration must be positive")
        if not callable(ease) or (
            on_complete is not None and not callable(on_complete)
        ):
            raise TypeError("ease and on_complete must be callable")
        self._ease = ease
        self._on_complete = on_complete
        self._elapsed = 0.0
        self._value = self._start

    @property
    def value(self) -> float:
        return self._value

    def _dispose(self) -> None:
        self._ease = linear
        self._on_complete = None

    def _advance(self, dt: float) -> Callable[[], None] | None:
        elapsed = min(self._duration, self._elapsed + dt)
        if elapsed == self._elapsed:
            return None
        if elapsed >= self._duration:
            self._elapsed = elapsed
            self._value = self._end
            self._done = True
            callback = self._on_complete
            self._dispose()
            return callback
        eased = _finite("easing result", self._ease(elapsed / self._duration))
        value = (
            self._start
            if self._start == self._end
            else (1 - eased) * self._start + eased * self._end
        )
        value = _finite("interpolated value", value)
        if not self.done:  # A custom easing function may cancel/clear its owner.
            self._elapsed, self._value = elapsed, value
        return None


class Timer(_Task):
    """One notification after a delay. A zero delay fires on the next update."""

    def __init__(self, delay: float, callback: Callable[[], None]):
        super().__init__()
        self._delay = _finite("delay", delay)
        if self._delay < 0:
            raise ValueError("delay must be nonnegative")
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callback = callback
        self._elapsed = 0.0

    def _dispose(self) -> None:
        self._callback = None

    def _advance(self, dt: float) -> Callable[[], None] | None:
        self._elapsed = min(self._delay, self._elapsed + dt)
        if self._elapsed >= self._delay:
            self._done = True
            callback = self._callback
            self._dispose()
            return callback
        return None


class Timeline:
    """Advance in seconds explicitly; no clock, threads or object mutation magic.

    Call update only when the owning scene should run, and clear on scene exit.
    Tasks run in insertion order over a snapshot; callback additions start next
    update, even at zero delay. clear cancels unvisited tasks immediately.
    Completion settles value/done before notifying. Cancellation never notifies.

    Easing receives progress strictly between 0 and 1; exact start/end values
    are preserved. Finite overshoot is allowed. Any easing/callback failure
    cancels every remaining task (including callback additions), then propagates.
    The timeline is reusable afterward. Invalid dt is rejected before work and
    leaves tasks intact. Recursive update is rejected.
    """

    def __init__(self):
        self._tasks: list[_Task] = []
        self._updating = False

    @property
    def pending_count(self) -> int:
        return sum(not task.done for task in self._tasks)

    def tween(
        self,
        start: float,
        end: float,
        duration: float,
        *,
        ease: Callable[[float], float] = linear,
        on_complete: Callable[[], None] | None = None,
    ) -> Tween:
        task = Tween(start, end, duration, ease=ease, on_complete=on_complete)
        self._tasks.append(task)
        return task

    def call_later(self, delay: float, callback: Callable[[], None]) -> Timer:
        task = Timer(delay, callback)
        self._tasks.append(task)
        return task

    def clear(self) -> None:
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    def update(self, dt: float) -> None:
        if self._updating:
            raise RuntimeError("recursive Timeline.update is not allowed")
        dt = _finite("dt", dt)
        if dt < 0:
            raise ValueError("dt must be nonnegative")
        self._updating = True
        try:
            for task in tuple(self._tasks):
                if not task.done:
                    callback = task._advance(dt)
                    if callback is not None and not task.cancelled:
                        callback()
        except BaseException:
            self.clear()
            raise
        finally:
            self._tasks = [task for task in self._tasks if not task.done]
            self._updating = False
