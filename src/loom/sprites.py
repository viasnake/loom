"""Uniform sprite clips and explicit, callback-free frame playback."""

from dataclasses import dataclass
from math import isfinite, nextafter


def _number(value, name):
    try:
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError
        return float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None


@dataclass(frozen=True, slots=True)
class SpriteClip:
    """Immutable source rectangles (u, v, w, h), all played at the same fps.

    Coordinates are nonnegative, dimensions positive integers. Source bounds
    are not checked: the game owns its sheet and Pyxel handles source clipping.
    Negative dimensions/flipping, image ownership and drawing are not managed.
    fps and the resulting total duration must be finite and positive.
    """

    frames: tuple[tuple[int, int, int, int], ...]
    fps: float = 8.0

    def __post_init__(self):
        frames = tuple(tuple(frame) for frame in self.frames)
        if not frames or any(
            len(frame) != 4
            or any(type(value) is not int for value in frame)
            or frame[0] < 0
            or frame[1] < 0
            or frame[2] <= 0
            or frame[3] <= 0
            for frame in frames
        ):
            raise ValueError("frames must be nonempty (u, v, w, h) integer rectangles")
        fps = _number(self.fps, "fps")
        if fps <= 0 or not isfinite(len(frames) / fps) or len(frames) / fps <= 0:
            raise ValueError("fps must give a finite positive clip duration")
        object.__setattr__(self, "frames", frames)
        object.__setattr__(self, "fps", fps)

    @classmethod
    def from_grid(
        cls,
        frame_size: tuple[int, int],
        *,
        columns: int,
        count: int,
        origin: tuple[int, int] = (0, 0),
        spacing: tuple[int, int] = (0, 0),
        fps: float = 8.0,
    ) -> "SpriteClip":
        """Build row-major frames from a regular sheet, without loading an image.

        columns is the number of frames per row, count the total to include.
        origin locates the first frame; spacing is the gap between frames, not
        an outer margin. A partial final row is allowed. Sheet bounds remain
        the caller's responsibility, as with explicitly supplied rectangles.
        """
        for name, value in (("columns", columns), ("count", count)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        pairs = []
        for name, value, minimum in (
            ("frame_size", frame_size, 1),
            ("origin", origin, 0),
            ("spacing", spacing, 0),
        ):
            try:
                pair = tuple(value)
            except TypeError:
                raise ValueError(
                    f"{name} must contain two integers >= {minimum}"
                ) from None
            if len(pair) != 2 or any(type(n) is not int or n < minimum for n in pair):
                raise ValueError(f"{name} must contain two integers >= {minimum}")
            pairs.append(pair)
        (width, height), (x, y), (gap_x, gap_y) = pairs
        return cls(
            tuple(
                (
                    x + (i % columns) * (width + gap_x),
                    y + (i // columns) * (height + gap_y),
                    width,
                    height,
                )
                for i in range(count)
            ),
            fps=fps,
        )

    @property
    def duration(self) -> float:
        return len(self.frames) / self.fps


class SpritePlayer:
    """A discrete frame cursor; advance only when the owning scene is active.

    No clock, Timeline, callbacks or intermediate-frame events are installed.
    Large dt skips directly to the resulting frame in bounded work. Once mode
    holds its last frame and finishes only after that frame's time has elapsed.
    Floating-point timing uses no epsilon boundary correction. Use a new player
    to switch clips; clips can be shared, playback state is always independent.
    """

    def __init__(self, clip: SpriteClip, *, loop: bool = True):
        if not isinstance(clip, SpriteClip):
            raise TypeError("clip must be a SpriteClip")
        if type(loop) is not bool:
            raise TypeError("loop must be a bool")
        self._clip, self._loop = clip, loop
        self._phase = 0.0

    @property
    def clip(self) -> SpriteClip:
        return self._clip

    @property
    def loop(self) -> bool:
        return self._loop

    @property
    def index(self) -> int:
        return min(int(self._phase), len(self.clip.frames) - 1)

    @property
    def frame(self) -> tuple[int, int, int, int]:
        return self.clip.frames[self.index]

    @property
    def finished(self) -> bool:
        return not self.loop and self._phase >= len(self.clip.frames)

    def restart(self) -> None:
        self._phase = 0.0

    def update(self, dt: float) -> None:
        dt = _number(dt, "dt")
        if dt < 0:
            raise ValueError("dt must be nonnegative")
        if dt == 0 or self.finished:
            return
        count = len(self.clip.frames)
        if not self.loop:
            if dt >= (count - self._phase) / self.clip.fps:
                self._phase = float(count)
            else:
                self._phase = min(
                    nextafter(float(count), 0), self._phase + dt * self.clip.fps
                )
            return
        # Reduce whole cycles before multiplication; even huge finite dt stays bounded.
        remainder = dt % self.clip.duration if dt >= self.clip.duration else dt
        # Decide wrap in time units before multiplication can round up a phase.
        remaining_time = (count - self._phase) / self.clip.fps
        phase = (
            (remainder - remaining_time) * self.clip.fps
            if remainder >= remaining_time
            else self._phase + remainder * self.clip.fps
        )
        self._phase = min(nextafter(float(count), 0), phase)
