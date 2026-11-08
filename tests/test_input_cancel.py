import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from loom import ActionMap, Button, Column, GameApp, Scene, Slider, UIRouter


class CancelTests(unittest.TestCase):
    def sample(self, actions, down=(), pointer=(10, 10)):
        return actions.sample(set(down).__contains__, pointer=pointer)

    def test_cancel_notifies_once_and_waits_for_release(self):
        actions = ActionMap({"charge": [1]})
        self.sample(actions, [1])
        actions.cancel()
        actions.cancel()
        cancelled = self.sample(actions, [1])
        self.assertEqual(cancelled.cancelled, {"charge"})
        self.assertEqual(cancelled.released, {"charge"})
        self.assertFalse(cancelled.held | cancelled.pressed)
        self.assertFalse(self.sample(actions, [1]).cancelled)
        self.assertFalse(self.sample(actions).released)
        self.assertEqual(self.sample(actions, [1]).pressed, {"charge"})

    def test_cancel_before_first_sample_suppresses_opener(self):
        actions = ActionMap({"fire": [1]})
        actions.cancel()
        first = self.sample(actions, [1])
        self.assertFalse(first.held | first.pressed | first.cancelled)
        self.sample(actions)
        self.assertEqual(self.sample(actions, [1]).pressed, {"fire"})

    def test_cancel_and_reset_both_orders_keep_notification(self):
        for order in (("reset", "cancel"), ("cancel", "reset")):
            with self.subTest(order=order):
                actions = ActionMap({"fire": [1]})
                self.sample(actions, [1])
                for method in order:
                    getattr(actions, method)()
                cancelled = self.sample(actions, [1])
                self.assertEqual(cancelled.cancelled, {"fire"})
                self.assertFalse(cancelled.held)
                self.sample(actions)
                self.assertEqual(self.sample(actions, [1]).pressed, {"fire"})

    def test_reset_alone_keeps_existing_resynchronization_contract(self):
        actions = ActionMap({"fire": [1]})
        self.sample(actions, [1])
        actions.reset()
        result = self.sample(actions, [1])
        self.assertEqual(result.held, {"fire"})
        self.assertFalse(result.pressed | result.released | result.cancelled)

    def test_cancel_and_replace_both_orders(self):
        for order in ("cancel_first", "replace_first"):
            with self.subTest(order=order):
                actions = ActionMap({"old": [1]})
                self.sample(actions, [1])
                if order == "cancel_first":
                    actions.cancel()
                actions.replace_bindings({"new": [2]})
                actions.cancel()
                result = self.sample(actions, [2])
                self.assertEqual(result.cancelled, {"old"})
                self.assertFalse(result.held)
                self.sample(actions)
                self.assertEqual(self.sample(actions, [2]).pressed, {"new"})

    def test_cancel_suppresses_raw_edges_but_keeps_raw_down_snapshot(self):
        actions = ActionMap({"fire": [1]}, watched_keys=[2])
        self.sample(actions, [1])
        actions.cancel()
        self.sample(actions, [1, 2])
        self.assertEqual(actions.physical_held, {1, 2})
        self.assertFalse(actions.physical_pressed)
        self.sample(actions)
        self.sample(actions, [2])
        self.assertEqual(actions.physical_pressed, {2})

    def test_rebind_raw_edges_not_changed_by_shared_cancel_mechanism(self):
        actions = ActionMap({"fire": [1]})
        self.sample(actions, [1])
        actions.replace_bindings({"new": [2]})
        self.sample(actions, [2])
        self.assertEqual(actions.physical_pressed, {2})

    def test_button_capture_cancels_without_commit_then_fresh_click_works(self):
        clicks = []
        router = UIRouter([Column([Button("Fire", lambda: clicks.append(True))])])
        actions = ActionMap({"primary": [1]})
        router.update(self.sample(actions, [1]))
        actions.cancel()
        router.update(self.sample(actions, [1]))
        router.update(self.sample(actions))
        self.assertEqual(clicks, [])
        router.update(self.sample(actions, [1]))
        router.update(self.sample(actions))
        self.assertEqual(clicks, [True])

    def test_slider_cancellation_does_not_apply_release_position(self):
        values = []
        slider = Slider("Volume", on_change=values.append)
        router = UIRouter([Column([slider], width=120)])
        actions = ActionMap({"primary": [1]})
        router.update(self.sample(actions, [1], pointer=(50, 10)))
        value = slider.value
        actions.cancel()
        router.update(self.sample(actions, [1], pointer=(110, 10)))
        router.update(self.sample(actions, pointer=(110, 10)))
        self.assertEqual(slider.value, value)
        self.assertEqual(len(values), 1)

    def test_routed_game_hold_receives_cancellation_not_confirming_release(self):
        router = UIRouter()
        actions = ActionMap({"charge": [1]})
        self.assertEqual(
            router.update(self.sample(actions, [1])).remaining.pressed, {"charge"}
        )
        actions.cancel()
        result = router.update(self.sample(actions, [1])).remaining
        self.assertEqual(result.released, {"charge"})
        self.assertEqual(result.cancelled, {"charge"})
        self.assertFalse(result.held)

    def test_cancel_suppresses_only_interrupted_samples_wheel(self):
        actions = ActionMap({"fire": [1]})
        actions.cancel()
        frame = actions.sample(lambda key: False, pointer=(2, 3), wheel=4)
        self.assertEqual(frame.wheel, 0)
        self.assertEqual(frame.pointer, (2, 3))
        self.assertFalse(frame.cancelled)
        self.assertEqual(actions.sample(lambda key: False, wheel=4).wheel, 4)
        actions.replace_bindings({"new": [2]})
        self.assertEqual(actions.sample(lambda key: False, wheel=4).wheel, 4)
        actions.reset()
        self.assertEqual(actions.sample(lambda key: False, wheel=4).wheel, 4)


class RuntimeCancelTests(unittest.TestCase):
    def engine(self):
        self.down = {1}
        return SimpleNamespace(
            KEY_NONE=0,
            init=lambda *a, **k: None,
            mouse=lambda visible: None,
            mouse_wheel=0,
            mouse_x=0,
            mouse_y=0,
            btn=lambda key: key in self.down,
            Image=lambda w, h: (w, h),
        )

    def test_pre_run_request_applies_before_first_sample(self):
        seen = []

        class Probe(Scene):
            def update(self, frame, dt):
                seen.append(frame)

        app = GameApp("test", Probe(), bindings={"fire": [1]})
        engine = self.engine()

        def run(update, draw):
            update()
            self.down.clear()
            update()
            self.down.add(1)
            update()

        engine.run = run
        app.request_input_cancel()
        app.request_input_cancel()
        with patch.dict(sys.modules, {"pyxel": engine}):
            app.run(headless=True)
        self.assertFalse(seen[0].held | seen[0].pressed)
        self.assertEqual(seen[2].pressed, {"fire"})

    def test_scene_request_preserves_current_frame_and_applies_next(self):
        seen = []

        class Probe(Scene):
            def update(self, frame, dt):
                seen.append(frame)
                if len(seen) == 1:
                    app.request_input_cancel()
                    app.request_input_cancel()
                    self_assert(frame.pressed, {"fire"})

        self_assert = self.assertEqual
        app = GameApp("test", Probe(), bindings={"fire": [1]})
        engine = self.engine()
        engine.run = lambda update, draw: (update(), update(), update())
        with patch.dict(sys.modules, {"pyxel": engine}):
            app.run(headless=True)
        self.assertEqual(seen[1].cancelled, {"fire"})
        self.assertFalse(seen[2].held | seen[2].cancelled)
