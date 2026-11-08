import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from loom import Scene, InputFrame
from loom.runtime import GameApp
from loom.display import DisplayConfig, PyxelDisplay
from loom.input import ActionMap
from loom.app import SceneStack


class Probe(Scene):
    def update(self, frame, dt):
        self.last = frame

    def exit(self):
        self.closed = True


class RuntimeTests(unittest.TestCase):
    def make_app(self):
        scene = Probe()
        app = GameApp("test", scene)
        engine = SimpleNamespace(
            mouse_x=3,
            mouse_y=1,
            btn=lambda key: False,
            Image=lambda w, h: (w, h),
            resize=lambda *args: None,
            quit=lambda: None,
        )
        app.display = PyxelDisplay(engine, DisplayConfig((20, 20), (4, 2)))
        app.actions = ActionMap({})
        app.scenes = SceneStack(scene, app.request_quit)
        return app, scene, engine

    def test_world_pointer_and_letterbox(self):
        app, scene, engine = self.make_app()
        with patch.dict(sys.modules, {"pyxel": engine}):
            app._update()
            self.assertIsNone(scene.last.world_pointer)
            engine.mouse_y = 10
            app._update()
            self.assertEqual(scene.last.world_pointer, (0.6, 1.0))

    def test_quit_closes_scene_before_native_exit(self):
        app, scene, engine = self.make_app()
        engine.quit = lambda: self.assertTrue(scene.closed)
        app.request_quit()
        with patch.dict(sys.modules, {"pyxel": engine}):
            app._update()

    def test_latest_resize_request_applies_after_update(self):
        app, scene, engine = self.make_app()
        observed = []
        coordinates = []
        engine.mouse_y = 10
        original_world = app.display.world
        first = DisplayConfig((24, 24), (4, 2))
        latest = DisplayConfig((40, 20), (4, 2))

        def update(frame, dt):
            coordinates.append(frame.world_pointer)
            observed.append(app.display.config)
            app.request_display(first)
            app.request_display(latest)
            observed.append(app.display.config)

        scene.update = update
        previous = app.display.config
        with patch.dict(sys.modules, {"pyxel": engine}):
            app._update()
        self.assertEqual(observed, [previous, previous])
        self.assertEqual(app.display.config, latest)
        self.assertIs(app.display.world, original_world)
        self.assertIsNone(app._resize_request)
        scene.update = lambda frame, dt: coordinates.append(frame.world_pointer)
        with patch.dict(sys.modules, {"pyxel": engine}):
            app._update()
        self.assertEqual(coordinates, [(0.6, 1.0), (0.3, 1.0)])

    def test_resize_failure_preserves_active_display(self):
        app, scene, engine = self.make_app()
        previous = app.display.config

        def fail_resize(*args):
            raise RuntimeError("backend resize failed")

        engine.resize = fail_resize
        app.request_display(DisplayConfig((40, 20), (4, 2)))
        with patch.dict(sys.modules, {"pyxel": engine}):
            with self.assertRaisesRegex(RuntimeError, "backend resize failed"):
                app._update()
        self.assertEqual(app.display.config, previous)

    def test_without_preserves_coordinates(self):
        frame = InputFrame(pressed=frozenset({"shoot"}), world_pointer=(1, 2))
        self.assertEqual(frame.without({"shoot"}).world_pointer, (1, 2))
        self.assertFalse(frame.without({"shoot"}).pressed)


class RuntimeConfigurationTests(unittest.TestCase):
    def test_empty_bindings_are_not_replaced_by_defaults(self):
        engine = SimpleNamespace(
            KEY_NONE=0,
            init=lambda *args, **kwargs: None,
            mouse=lambda visible: None,
            Image=lambda width, height: (width, height),
            run=lambda update, draw: None,
        )
        app = GameApp("test", Probe(), bindings={})
        with patch.dict(sys.modules, {"pyxel": engine}):
            app.run(headless=True)
        self.assertEqual(app.actions.bindings, {})

    def test_frame_rate_requires_integer(self):
        for fps in (True, 60.5, 0, 241):
            with self.assertRaises(ValueError):
                GameApp("test", Probe(), fps=fps)


class RuntimeFailureTests(unittest.TestCase):
    def test_callback_and_cleanup_failures_are_both_preserved(self):
        for failing_hook in ("update", "draw"):
            with self.subTest(failing_hook=failing_hook):
                calls = []

                class Broken(Scene):
                    def update(self, frame, dt):
                        calls.append("update")
                        if failing_hook == "update":
                            raise ValueError("gameplay failed")

                    def draw(self, display):
                        calls.append("draw")
                        raise ValueError("render failed")

                    def exit(self):
                        calls.append("exit")
                        raise OSError("resource cleanup failed")

                def run(update, draw):
                    update()
                    draw()
                    update()

                engine = SimpleNamespace(
                    KEY_NONE=0,
                    init=lambda *args, **kwargs: None,
                    mouse=lambda visible: None,
                    mouse_x=0,
                    mouse_y=0,
                    btn=lambda key: False,
                    Image=lambda width, height: (width, height),
                    run=run,
                )
                app = GameApp("failure test", Broken(), bindings={})
                with patch.dict(sys.modules, {"pyxel": engine}):
                    with self.assertRaises(ExceptionGroup) as caught:
                        app.run(headless=True)
                execution, cleanup = caught.exception.exceptions
                self.assertIsInstance(execution, ValueError)
                self.assertIsInstance(cleanup, ExceptionGroup)
                self.assertIsInstance(cleanup.exceptions[0], OSError)
                expected = (
                    ["update", "exit"]
                    if failing_hook == "update"
                    else ["update", "draw", "exit"]
                )
                self.assertEqual(calls, expected)
                app.scenes.close()
                self.assertEqual(calls, expected)
