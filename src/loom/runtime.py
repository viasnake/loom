"""The optional Pyxel boundary. Pure game rules need not import Pyxel."""
from .app import Scene, SceneStack
from .input import ActionMap
from .display import DisplayConfig, PyxelDisplay


class GameApp:
    def __init__(self, title: str, initial_scene: Scene,
                 display: DisplayConfig | None = None, fps: int = 60,
                 bindings: dict[str, tuple[int, ...]] | None = None):
        if not 1 <= fps <= 240:
            raise ValueError("fps must be between 1 and 240")
        self.title, self.initial_scene = title, initial_scene
        self.config = display or DisplayConfig()
        self.fps, self.bindings = fps, bindings
        self._resize_request = None
        self._quit_requested = False

    def request_quit(self) -> None:
        self._quit_requested = True

    def request_display(self, config: DisplayConfig) -> None:
        self._resize_request = config

    def run(self, *, headless: bool = False) -> None:
        import pyxel
        pyxel.init(*self.config.output_size, title=self.title, fps=self.fps,
                   quit_key=pyxel.KEY_NONE, capture_sec=0, headless=headless)
        pyxel.mouse(True)
        self.display = PyxelDisplay(pyxel, self.config)
        bindings = self.bindings or {
            "confirm": (pyxel.KEY_RETURN, pyxel.GAMEPAD1_BUTTON_A),
            "cancel": (pyxel.KEY_ESCAPE, pyxel.GAMEPAD1_BUTTON_B),
            "next": (pyxel.KEY_TAB, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN),
            "previous": (pyxel.GAMEPAD1_BUTTON_DPAD_UP,),
            "primary": (pyxel.MOUSE_BUTTON_LEFT,),
            "left": (pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT),
            "right": (pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT),
        }
        self.actions = ActionMap(bindings)
        self.scenes = SceneStack(self.initial_scene, self.request_quit)
        try:
            pyxel.run(self._update, self._draw)
        finally:
            self.scenes.close()

    def _update(self) -> None:
        import pyxel
        pointer = (pyxel.mouse_x, pyxel.mouse_y)
        frame = self.actions.sample(pyxel.btn, pointer, self.display.viewport.to_local(*pointer))
        self.scenes.update(frame, 1 / self.fps)
        if self._quit_requested:
            # Pyxel may terminate the process: clean up BEFORE calling quit.
            self.scenes.close()
            pyxel.quit()
            return
        if self._resize_request is not None:
            self.display.resize(self._resize_request)
            self.config = self._resize_request
            self._resize_request = None

    def _draw(self) -> None:
        # A scene may draw directly through Pyxel, or through display.world and
        # display.composite() before drawing high-resolution UI.
        self.scenes.draw(self.display)
