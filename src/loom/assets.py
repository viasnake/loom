"""Stable file paths for trusted filesystem and packaged resources."""

from contextlib import ExitStack
from importlib import resources
from pathlib import Path
from types import ModuleType
from zipfile import Path as ZipPath


def _parts(name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(name, str):
        raise TypeError("resource names must be strings")
    if allow_empty and name == "":
        return ()
    parts = tuple(name.split("/"))
    if (
        "\\" in name
        or ":" in name
        or "\x00" in name
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ValueError(
            "resource names must be nonempty relative POSIX paths without traversal"
        )
    return parts


def _within(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("resource symlink escapes its asset root")
    return resolved


class AssetStore:
    """Anchor paths before engine initialization or working-directory changes.

    Only files are returned. Relative names cannot traverse out of the selected
    root; filesystem symlinks escaping it are rejected when resolving a name.
    This is convenience for trusted resources, not a sandbox or TOCTOU defense.
    Do not modify resource files/archives while using the store.

    from_package supports standard directory and zip packages, not namespace or
    custom resource loaders. Zip files are materialized once per name, and remain
    available until close. Load resources within that lifetime; paths retained
    afterward may no longer exist. Filesystem originals are never deleted.
    """

    def __init__(self, root: str | Path):
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(root)
        self._initialize(root)

    def _initialize(self, root: Path | ZipPath) -> None:
        self._root: Path | ZipPath | None = root
        self._paths: dict[str, Path] = {}
        self._stack = ExitStack()
        self._closed = False

    @classmethod
    def from_package(
        cls, package: str | ModuleType, directory: str = ""
    ) -> "AssetStore":
        parts = _parts(directory, allow_empty=True)
        root = resources.files(package)
        with ExitStack() as pending:
            # files() opens a zip archive for this resource tree. Own that file
            # handle explicitly: callers/mocks can retain descendant ZipPaths.
            # Register first so extracted files are cleaned before archive close.
            if isinstance(root, ZipPath):
                pending.callback(root.root.close)
            if isinstance(root, Path):
                package_root = root.resolve(strict=True)
                root = _within(root.joinpath(*parts), package_root)
            elif isinstance(root, ZipPath):
                if parts:
                    root = root.joinpath(*parts)
            else:
                raise TypeError(
                    "only standard directory and zip packages are supported"
                )
            if not root.is_dir():
                raise NotADirectoryError(str(root))
            store = cls.__new__(cls)
            store._initialize(root)
            store._stack = pending.pop_all()
            return store

    @property
    def closed(self) -> bool:
        return self._closed

    def path(self, name: str) -> Path:
        if self.closed:
            raise RuntimeError("AssetStore is closed")
        parts = _parts(name)
        root = self._root
        if isinstance(root, Path):
            path = _within(root.joinpath(*parts), root)
            if not path.is_file():
                raise IsADirectoryError(path)
            return path
        if name in self._paths:
            return self._paths[name]
        resource = root.joinpath(*parts)
        if not resource.is_file():
            if resource.is_dir():
                raise IsADirectoryError(name)
            raise FileNotFoundError(name)
        path = self._stack.enter_context(resources.as_file(resource))
        self._paths[name] = path
        return path

    def close(self) -> None:
        if self.closed:
            return
        self._closed = True
        self._paths.clear()
        self._root = None
        self._stack.close()

    def __enter__(self) -> "AssetStore":
        if self.closed:
            raise RuntimeError("AssetStore is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False
