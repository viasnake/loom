"""Named colours resolved once into Pyxel's single global 256-colour palette."""
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


class Palette:
    """Immutable, insertion-ordered palette; equal RGB colours share an index.

    Build the entire palette before loading images or GLB assets. Asset loaders
    must not use include_colors=True afterwards. Applying a different palette
    requires rebuilding Cube shading and palette-dependent game resources.
    """

    def __init__(self, colors: Mapping[str, int]) -> None:
        if not colors:
            raise ValueError("palette must contain at least one colour")
        values: list[int] = []
        rgb_indices: dict[int, int] = {}
        indices: dict[str, int] = {}
        for name, rgb in colors.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("colour names must be non-empty strings")
            if type(rgb) is not int or not 0 <= rgb <= 0xFFFFFF:
                raise ValueError(f"invalid RGB colour: {name}")
            if rgb not in rgb_indices:
                if len(values) == 256:
                    raise ValueError("Pyxel supports at most 256 simultaneous palette colours")
                rgb_indices[rgb] = len(values)
                values.append(rgb)
            indices[name] = rgb_indices[rgb]
        self.colors = tuple(values)
        self.names = MappingProxyType(indices)

    def index(self, name: str) -> int:
        return self.names[name]

    def __getitem__(self, name: str) -> int:
        return self.index(name)

    def apply(self, pyxel: Any) -> None:
        """Explicit global palette change; call before loading palette-mapped assets."""
        pyxel.colors[:] = self.colors
