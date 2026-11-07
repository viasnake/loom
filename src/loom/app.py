"""Scene stack independent of Pyxel; transitions apply after the update."""
from dataclasses import dataclass
from .input import InputFrame


class Scene:
    blocks_update_below = True
    opaque = True

    def enter(self, scenes: "SceneStack") -> None:
        self.scenes = scenes

    def exit(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def resume(self) -> None:
        pass

    def update(self, frame: InputFrame, dt: float) -> None:
        pass

    def draw(self, target) -> None:
        pass


class SceneStack:
    """Only the top scene receives input. Lower updates receive an empty frame.

    A single transition may be queued per update: conflicting transitions fail
    rather than accidentally executing twice. Draw must not queue transitions.
    """
    def __init__(self, initial: Scene, on_quit=None):
        self._on_quit = on_quit
        self._scenes: list[Scene] = [initial]
        self._pending: tuple[str, Scene | None] | None = None
        self._drawing = False
        initial.enter(self)

    @property
    def current(self) -> Scene:
        return self._scenes[-1]

    def _request(self, operation: str, scene: Scene | None = None) -> None:
        if self._drawing:
            raise RuntimeError("Scene changes are not permitted during draw")
        if self._pending is not None:
            raise RuntimeError("A scene change is already queued")
        if operation == "pop" and len(self._scenes) == 1:
            raise RuntimeError("Cannot pop the root scene")
        if scene is not None and scene in self._scenes:
            raise ValueError("A scene instance cannot be pushed twice")
        self._pending = operation, scene

    def quit(self) -> None:
        if self._on_quit is None:
            raise RuntimeError("No application quit handler installed")
        self._on_quit()

    def push(self, scene: Scene) -> None:
        self._request("push", scene)

    def replace(self, scene: Scene) -> None:
        self._request("replace", scene)

    def pop(self) -> None:
        self._request("pop")

    def update(self, frame: InputFrame, dt: float) -> None:
        if dt < 0:
            raise ValueError("dt must be non-negative")
        start = len(self._scenes) - 1
        while start > 0 and not self._scenes[start].blocks_update_below:
            start -= 1
        for index in range(start, len(self._scenes)):
            self._scenes[index].update(frame if index == len(self._scenes)-1 else InputFrame(), dt)
        self._apply()

    def _apply(self) -> None:
        if self._pending is None:
            return
        operation, scene = self._pending
        self._pending = None
        if operation == "push":
            self.current.pause()
            self._scenes.append(scene)
            scene.enter(self)
        elif operation == "replace":
            self.current.exit()
            self._scenes[-1] = scene
            scene.enter(self)
        else:
            self._scenes.pop().exit()
            self.current.resume()

    def draw(self, target) -> None:
        start = len(self._scenes) - 1
        while start > 0 and not self._scenes[start].opaque:
            start -= 1
        self._drawing = True
        try:
            for scene in self._scenes[start:]:
                scene.draw(target)
        finally:
            self._drawing = False

    def close(self) -> None:
        self._pending = None
        while self._scenes:
            self._scenes.pop().exit()
