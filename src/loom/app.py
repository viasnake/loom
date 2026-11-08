"""Scene stack independent of Pyxel; transitions apply after the update."""

from collections.abc import Callable
import math
from .input import InputFrame


class Scene:
    """Subclass hooks for one screen; call ``super().enter(scenes)`` when overriding.

    Set ``opaque=False`` to draw lower screens, and ``blocks_update_below=False``
    to keep them updating. These switches are independent; only the top screen
    receives input. Exit must tolerate partially completed initialization.
    """

    blocks_update_below = True
    opaque = True

    def enter(self, scenes: "SceneStack") -> None:
        """Attach to the stack before the first update or draw."""
        self.scenes = scenes

    def exit(self) -> None:
        """Release screen-owned resources on removal or application shutdown."""
        pass

    def pause(self) -> None:
        """Called before another screen is pushed over this one."""
        pass

    def resume(self) -> None:
        """Called after the covering screen is popped."""
        pass

    def update(self, frame: InputFrame, dt: float) -> None:
        pass

    def draw(self, target) -> None:
        pass


class SceneStack:
    """Only the top scene receives input. Lower updates receive an empty frame.

    A callback failure is fatal to the current update; callers must close the
    stack rather than continue using it. GameApp performs that cleanup.

    A single transition may be queued per update: conflicting transitions fail
    rather than accidentally executing twice. Draw must not queue transitions.
    """

    def __init__(self, initial: Scene, on_quit: Callable[[], None] | None = None):
        self._on_quit = on_quit
        self._scenes: list[Scene] = [initial]
        self._pending: tuple[str, Scene | None] | None = None
        self._drawing = False
        self._closed = False
        try:
            initial.enter(self)
        except BaseException as initialization_error:
            try:
                self.close()
            except BaseException as cleanup_error:
                raise BaseExceptionGroup(
                    "Scene initialization and cleanup failed",
                    [initialization_error, cleanup_error],
                ) from None
            raise

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("Scene stack is closed")

    @property
    def current(self) -> Scene:
        self._require_open()
        return self._scenes[-1]

    def _request(self, operation: str, scene: Scene | None = None) -> None:
        self._require_open()
        if self._drawing:
            raise RuntimeError("Scene changes are not permitted during draw")
        if self._pending is not None:
            raise RuntimeError("A scene change is already queued")
        if operation == "pop" and len(self._scenes) == 1:
            raise RuntimeError("Cannot pop the root scene")
        if scene is not None and any(scene is active for active in self._scenes):
            raise ValueError("A scene instance cannot be pushed twice")
        self._pending = operation, scene

    def quit(self) -> None:
        self._require_open()
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
        self._require_open()
        if not math.isfinite(dt) or dt < 0:
            raise ValueError("dt must be finite and non-negative")
        start = len(self._scenes) - 1
        while start > 0 and not self._scenes[start].blocks_update_below:
            start -= 1
        for index in range(start, len(self._scenes)):
            self._scenes[index].update(
                frame if index == len(self._scenes) - 1 else InputFrame(), dt
            )
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
            previous = self._scenes.pop()
            previous.exit()
            self._scenes.append(scene)
            scene.enter(self)
        else:
            self._scenes.pop().exit()
            self.current.resume()

    def draw(self, target) -> None:
        self._require_open()
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
        """Exit every scene once, even if another exit fails.

        Closing is idempotent. All cleanup failures are preserved in a
        BaseExceptionGroup; callbacks cannot queue new work on a closed stack.
        """
        if self._closed:
            return
        self._closed = True
        self._pending = None
        errors = []
        while self._scenes:
            try:
                self._scenes.pop().exit()
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup("Scene cleanup failed", errors)
