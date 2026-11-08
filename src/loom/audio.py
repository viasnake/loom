"""Small channel-owned audio buses; no sound-resource or global mixer mutation."""

from collections.abc import Iterable, Mapping, Sequence
from math import isfinite
from typing import Any, Protocol


class AudioChannel(Protocol):
    gain: float

    def play(self, snd: Any, sec: float = 0, loop: bool = False) -> None: ...
    def play_pos(self) -> tuple[int, float] | None: ...
    def stop(self) -> None: ...


def _number(name: str, value: float) -> float:
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


def _volume(value: float) -> float:
    value = _number("volume", value)
    if not 0 <= value <= 1:
        raise ValueError("volume must be between 0 and 1")
    return value


def _muted(value: bool) -> bool:
    if type(value) is not bool:
        raise TypeError("muted must be a bool")
    return value


class Voice:
    """A playback token, not ownership of every future sound on the channel."""

    def __init__(self, mixer: "AudioMixer", channel: int, token: int):
        self._mixer, self._channel, self._token = mixer, channel, token

    @property
    def channel(self) -> int:
        return self._channel

    @property
    def active(self) -> bool:
        return (
            self._mixer._current(self._channel, self._token)
            and self._mixer._channels[self._channel].play_pos() is not None
        )

    def stop(self) -> None:
        if self._mixer._current(self._channel, self._token):
            self._mixer._stop_channels((self._channel,))


class AudioMixer:
    """Reserve idle, disjoint channel pools and preserve their baseline gains.

    Pass pyxel.channels after engine initialization, or compatible test channels.
    Owned channels must be used exclusively by this mixer until close; raw play,
    gain writes or a second mixer on the same objects invalidate this contract.
    Full buses return None instead of stealing voices. Volume scales each captured
    baseline gain, preserving Pyxel's default headroom. Mute does not stop playback.
    close stops only owned channels and restores their original gains. Cleanup
    attempts every operation and groups failures; repeated close is a no-op.
    """

    def __init__(
        self, channels: Sequence[AudioChannel], buses: Mapping[str, Iterable[int]]
    ):
        self._channels = tuple(channels)
        if not isinstance(buses, Mapping):
            raise TypeError("buses must be a mapping")
        normalized: dict[str, tuple[int, ...]] = {}
        owned: set[int] = set()
        for name, indices in buses.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("bus names must be nonempty strings")
            if isinstance(indices, (str, bytes, bytearray, Mapping)):
                raise TypeError("bus channels must be integer indices")
            indices = tuple(indices)
            if not indices or any(
                type(i) is not int or not 0 <= i < len(self._channels) for i in indices
            ):
                raise ValueError("each bus requires valid nonnegative channel indices")
            if len(set(indices)) != len(indices) or owned.intersection(indices):
                raise ValueError("bus channels must be disjoint, without duplicates")
            owned.update(indices)
            normalized[name] = indices
        self._buses = normalized
        self._owned = tuple(i for indices in normalized.values() for i in indices)
        owned_objects = {id(self._channels[i]) for i in self._owned}
        occurrences = sum(id(channel) in owned_objects for channel in self._channels)
        if len(owned_objects) != len(self._owned) or occurrences != len(self._owned):
            raise ValueError(
                "owned channel objects must not alias any supplied channel"
            )
        self._baseline: dict[int, float] = {}
        for i in self._owned:
            channel = self._channels[i]
            if any(
                not callable(getattr(channel, method, None))
                for method in ("play", "play_pos", "stop")
            ):
                raise TypeError("channels must provide play, play_pos and stop")
            gain = _number("channel gain", channel.gain)
            if gain < 0:
                raise ValueError("channel gain must be nonnegative")
            if channel.play_pos() is not None:
                raise ValueError("owned channels must be idle at construction")
            self._baseline[i] = gain
        self._volumes = dict.fromkeys(normalized, 1.0)
        self._muted = dict.fromkeys(normalized, False)
        self._master_volume = 1.0
        self._master_muted = False
        self._tokens = dict.fromkeys(self._owned, 0)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def _open(self) -> None:
        if self.closed:
            raise RuntimeError("AudioMixer is closed")

    def _current(self, channel: int, token: int) -> bool:
        return not self.closed and self._tokens.get(channel) == token

    def _apply(
        self,
        master: float,
        muted: bool,
        volumes: Mapping[str, float],
        bus_muted: Mapping[str, bool],
    ) -> None:
        self._open()
        previous = {i: self._channels[i].gain for i in self._owned}
        attempted: list[int] = []
        try:
            for name, indices in self._buses.items():
                multiplier = 0 if muted or bus_muted[name] else master * volumes[name]
                for i in indices:
                    attempted.append(i)
                    self._channels[i].gain = self._baseline[i] * multiplier
        except Exception as error:
            failures = [error]
            for i in reversed(attempted):
                try:
                    self._channels[i].gain = previous[i]
                except Exception as rollback_error:
                    failures.append(rollback_error)
            raise ExceptionGroup(
                "audio gain update failed; rollback attempted", failures
            ) from None

    @property
    def master_volume(self) -> float:
        return self._master_volume

    @master_volume.setter
    def master_volume(self, value: float) -> None:
        value = _volume(value)
        self._apply(value, self._master_muted, self._volumes, self._muted)
        self._master_volume = value

    @property
    def master_muted(self) -> bool:
        return self._master_muted

    @master_muted.setter
    def master_muted(self, value: bool) -> None:
        value = _muted(value)
        self._apply(self._master_volume, value, self._volumes, self._muted)
        self._master_muted = value

    def bus_volume(self, bus: str) -> float:
        return self._volumes[bus]

    def bus_muted(self, bus: str) -> bool:
        return self._muted[bus]

    def set_bus_volume(self, bus: str, value: float) -> None:
        self._buses[bus]
        values = {**self._volumes, bus: _volume(value)}
        self._apply(self._master_volume, self._master_muted, values, self._muted)
        self._volumes = values

    def set_bus_muted(self, bus: str, value: bool) -> None:
        self._buses[bus]
        values = {**self._muted, bus: _muted(value)}
        self._apply(self._master_volume, self._master_muted, self._volumes, values)
        self._muted = values

    def play(
        self, bus: str, sound: Any, *, sec: float = 0, loop: bool = False
    ) -> Voice | None:
        self._open()
        indices = self._buses[bus]
        sec = _number("sec", sec)
        if sec < 0:
            raise ValueError("sec must be nonnegative")
        if type(loop) is not bool:
            raise TypeError("loop must be a bool")
        for i in indices:
            channel = self._channels[i]
            if channel.play_pos() is not None:
                continue
            self._tokens[i] += 1
            try:
                channel.play(sound, sec=sec, loop=loop)
            except Exception as error:
                try:
                    channel.stop()
                except Exception as cleanup_error:
                    raise ExceptionGroup(
                        "audio play and cleanup failed", [error, cleanup_error]
                    ) from None
                raise
            return Voice(self, i, self._tokens[i])
        return None

    def _stop_channels(self, indices: Iterable[int]) -> None:
        failures = []
        for i in indices:
            self._tokens[i] += 1
            try:
                self._channels[i].stop()
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup("audio stop failed", failures)

    def stop(self, bus: str | None = None) -> None:
        self._open()
        self._stop_channels(self._owned if bus is None else self._buses[bus])

    def close(self) -> None:
        if self.closed:
            return
        self._closed = True
        failures = []
        for i in self._owned:
            try:
                self._channels[i].stop()
            except Exception as error:
                failures.append(error)
            try:
                self._channels[i].gain = self._baseline[i]
            except Exception as error:
                failures.append(error)
        if failures:
            raise ExceptionGroup("audio close failed", failures)
