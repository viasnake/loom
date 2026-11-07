"""Small synchronous JSON saves with explicit version migration and recovery.

``load`` never rewrites files. ``save`` preserves the previous valid file as
``.bak`` before atomically replacing the primary. A corrupt or newer primary
blocks saving; call ``recover`` explicitly for corruption. A directory must
have a single writer; concurrent saves are not supported.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Callable, Literal, Mapping


class SaveError(Exception):
    """A save cannot be read or safely replaced."""


class CorruptSaveError(SaveError):
    """The file is not a valid Loom save envelope."""


class FutureVersionError(SaveError):
    """This application is too old to interpret this save."""


class MigrationError(SaveError):
    """A required migration is absent or failed."""


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
}


def _name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not _NAME.fullmatch(value)
        or value.endswith(".")
        or ".." in value
        or value.split(".", 1)[0].upper() in _WINDOWS_RESERVED
    ):
        raise ValueError(
            "Use a portable name containing letters, digits, '.', '_' or '-'"
        )
    return value


@dataclass(frozen=True)
class AppPaths:
    """Stable OS paths; keep device settings out of cloud-synced progress."""

    progress: Path
    settings: Path

    @classmethod
    def for_app(cls, app_id: str) -> AppPaths:
        app_id = _name(app_id)
        home = Path.home()
        if sys.platform == "win32":
            shared = Path(os.environ.get("APPDATA") or home / "AppData/Roaming")
            local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData/Local")
            return cls(shared / app_id / "saves", local / app_id / "settings")
        if sys.platform == "darwin":
            base = home / "Library/Application Support" / app_id
            return cls(base / "saves", base / "settings")
        data = Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share")
        config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        # XDG explicitly requires absolute paths; a relative value is ignored.
        if not data.is_absolute():
            data = home / ".local/share"
        if not config.is_absolute():
            config = home / ".config"
        return cls(data / app_id / "saves", config / app_id / "settings")


Migration = Callable[[dict], dict]


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number: {value}")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"JSON number exceeds the finite float range: {value}")
    return number


class SaveStore:
    """Versioned JSON object storage, without dependencies or background threads.

    ``migrations[n]`` converts version n's data to version n+1. Callbacks receive
    a private copy. A failed callback cannot mutate an existing file. Save calls
    must run outside latency-sensitive update/draw callbacks for large data.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        version: int = 1,
        migrations: Mapping[int, Migration] | None = None,
    ):
        if type(version) is not int or version < 1:
            raise ValueError("version must be a positive integer")
        self.root = Path(root)
        self.version = version
        self.migrations = dict(migrations or {})
        if any(
            type(v) is not int or v < 1 or not callable(fn)
            for v, fn in self.migrations.items()
        ):
            raise ValueError("migrations map positive versions to functions")

    @classmethod
    def for_app(
        cls,
        app_id: str,
        *,
        kind: Literal["progress", "settings"] = "progress",
        version: int = 1,
        migrations: Mapping[int, Migration] | None = None,
    ) -> SaveStore:
        if kind not in ("progress", "settings"):
            raise ValueError("kind must be 'progress' or 'settings'")
        paths = AppPaths.for_app(app_id)
        return cls(getattr(paths, kind), version=version, migrations=migrations)

    def path(self, slot: str = "main") -> Path:
        return self.root / f"{_name(slot)}.json"

    @staticmethod
    def _read(path: Path) -> bytes:
        if path.is_symlink():
            raise SaveError(f"Refusing symbolic link: {path}")
        return path.read_bytes()

    def _decode(self, raw: bytes) -> tuple[int, dict]:
        try:
            envelope = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_bad_constant,
                parse_float=_finite_float,
            )
        except (UnicodeError, ValueError, RecursionError) as exc:
            raise CorruptSaveError("Invalid JSON save") from exc
        if (
            not isinstance(envelope, dict)
            or envelope.get("format") != "loom.save"
            or type(envelope.get("version")) is not int
            or envelope["version"] < 1
        ):
            raise CorruptSaveError("Invalid save envelope")
        version = envelope["version"]
        # A future format may add fields or change the shape of its data. Do not
        # mistake that for corruption and allow recovery to downgrade the file.
        if version > self.version:
            raise FutureVersionError(
                f"Save version {version} exceeds supported {self.version}"
            )
        if set(envelope) != {"format", "version", "data"} or not isinstance(
            envelope["data"], dict
        ):
            raise CorruptSaveError("Invalid save envelope")
        return version, envelope["data"]

    def _migrate(self, version: int, data: dict) -> dict:
        data = deepcopy(data)
        while version < self.version:
            migrate = self.migrations.get(version)
            if migrate is None:
                raise MigrationError(f"Missing migration from version {version}")
            try:
                data = migrate(data)
                self._encode(data)  # reject unsupported types and NaN immediately
            except Exception as exc:
                raise MigrationError(
                    f"Migration from version {version} failed"
                ) from exc
            version += 1
        return data

    def _encode(self, data: dict) -> bytes:
        if not isinstance(data, dict):
            raise TypeError("save data must be a JSON object")

        # JSON silently coerces non-string keys; reject this lossy conversion.
        def check(value: object) -> None:
            if isinstance(value, dict):
                if any(not isinstance(k, str) for k in value):
                    raise TypeError("JSON object keys must be strings")
                for item in value.values():
                    check(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    check(item)

        check(data)
        return (
            json.dumps(
                {"format": "loom.save", "version": self.version, "data": data},
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    def _replace(self, path: Path, raw: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise SaveError(f"Refusing symbolic link: {path}")
        fd, temporary = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=self.root
        )
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def load(self, slot: str = "main") -> dict:
        """Load and migrate in memory. Missing files raise FileNotFoundError."""
        return self._migrate(*self._decode(self._read(self.path(slot))))

    def save(self, data: dict, slot: str = "main") -> None:
        """Save, refusing to overwrite corrupt, newer or unmigratable primary files.

        Backup succeeds before primary replacement. On replacement failure the
        previous primary remains readable. File bytes are fsynced; atomic rename
        is not a guarantee against every filesystem/power-loss failure.
        """
        path = self.path(slot)
        raw = self._encode(data)
        try:
            previous = self._read(path)
        except FileNotFoundError:
            previous = None
        if previous is not None:
            self._migrate(*self._decode(previous))
            self._replace(path.with_suffix(".json.bak"), previous)
        self._replace(path, raw)

    def recover(self, slot: str = "main") -> dict:
        """Explicitly restore valid backup, retaining a bad primary as .rejected.

        Never downgrade a future-version primary. A valid primary is not rolled
        back; use another slot for deliberate rollback. Backup remains unchanged.
        """
        path = self.path(slot)
        backup = self._read(path.with_suffix(".json.bak"))
        data = self._migrate(*self._decode(backup))
        try:
            previous = self._read(path)
        except FileNotFoundError:
            previous = None
        if previous is not None:
            try:
                self._decode(previous)
            except CorruptSaveError:
                self._replace(path.with_suffix(".json.rejected"), previous)
            else:
                raise SaveError("Primary is valid; recovery is not necessary")
        self._replace(path, backup)
        return data
