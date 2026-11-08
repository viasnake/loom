"""The optional Pyxel boundary. Pure game rules need not import Pyxel."""

from collections.abc import Iterable, Mapping

from .app import Scene, SceneStack
from .input import ActionMap
from .display import DisplayConfig, PyxelDisplay


class GameApp:
    """Connect scenes to one Pyxel loop at a fixed update interval.

    ``bindings=None`` selects keyboard/mouse/gamepad defaults; an empty mapping
    disables all named actions. Rendering stays under the game's control.
    """

    def __init__(
        self,
        title: str,
        initial_scene: Scene,
        display: DisplayConfig | None = None,
        fps: int = 60,
        bindings: dict[str, tuple[int, ...]] | None = None,
    ):
        if type(fps) is not int or not 1 <= fps <= 240:
            raise ValueError("fps must be an integer between 1 and 240")
        self.title, self.initial_scene = title, initial_scene
        self.config = display or DisplayConfig()
        self.fps = fps
        self.bindings = None if bindings is None else ActionMap(bindings).bindings
        self._bindings_request = None
        self._resize_request = None
        self._quit_requested = False

    def request_quit(self) -> None:
        """Exit scenes after this update, before asking Pyxel to terminate."""
        self._quit_requested = True

    def request_display(self, config: DisplayConfig) -> None:
        """Queue a render-resolution change; the latest request wins."""
        self._resize_request = config

    def request_bindings(self, bindings: Mapping[str, Iterable[int]]) -> None:
        """Queue a validated, copied full action map; latest request wins.

        Applied after the current scene update, or before the first sample when
        requested before run. Existing held actions are cancelled on the next
        sample; new bindings held at application wait for release before firing.
        """
        self._bindings_request = ActionMap(bindings).bindings

    def run(self, *, headless: bool = False) -> None:
        """Initialize Pyxel and run. Native quit may terminate the process."""
        import pyxel

        pyxel.init(
            *self.config.output_size,
            title=self.title,
            fps=self.fps,
            quit_key=pyxel.KEY_NONE,
            capture_sec=0,
            headless=headless,
        )
        pyxel.mouse(True)
        self.display = PyxelDisplay(pyxel, self.config)
        bindings = (
            self.bindings
            if self.bindings is not None
            else {
                "confirm": (pyxel.KEY_RETURN, pyxel.GAMEPAD1_BUTTON_A),
                "cancel": (pyxel.KEY_ESCAPE, pyxel.GAMEPAD1_BUTTON_B),
                "next": (pyxel.KEY_TAB, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN),
                "previous": (pyxel.GAMEPAD1_BUTTON_DPAD_UP,),
                "primary": (pyxel.MOUSE_BUTTON_LEFT,),
                "decrement": (pyxel.KEY_LEFT, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT),
                "increment": (pyxel.KEY_RIGHT, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT),
                "left": (pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT),
                "right": (
                    pyxel.KEY_RIGHT,
                    pyxel.KEY_D,
                    pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT,
                ),
            }
        )
        if self._bindings_request is not None:
            bindings = self._bindings_request
            self._bindings_request = None
        self.actions = ActionMap(bindings)
        self.scenes = SceneStack(self.initial_scene, self.request_quit)
        try:
            pyxel.run(self._update, self._draw)
        except BaseException as run_error:
            try:
                self.scenes.close()
            except BaseException as cleanup_error:
                # Keep the gameplay failure visible alongside cleanup failures.
                # BaseExceptionGroup also preserves interrupts/SystemExit.
                raise BaseExceptionGroup(
                    "Application execution and cleanup failed",
                    [run_error, cleanup_error],
                ) from None
            raise
        else:
            self.scenes.close()

    def _update(self) -> None:
        import pyxel

        pointer = (pyxel.mouse_x, pyxel.mouse_y)
        frame = self.actions.sample(
            pyxel.btn,
            pointer,
            self.display.viewport.to_local(*pointer),
            pyxel.mouse_wheel,
        )
        self.scenes.update(frame, 1 / self.fps)
        if self._quit_requested:
            # Pyxel may terminate the process: clean up BEFORE calling quit.
            self.scenes.close()
            pyxel.quit()
            return
        if self._bindings_request is not None:
            self.actions.replace_bindings(self._bindings_request)
            self.bindings = self.actions.bindings
            self._bindings_request = None
        if self._resize_request is not None:
            self.display.resize(self._resize_request)
            self.config = self._resize_request
            self._resize_request = None

    def _draw(self) -> None:
        # A scene may draw directly through Pyxel, or through display.world and
        # display.composite() before drawing high-resolution UI.
        self.scenes.draw(self.display)
