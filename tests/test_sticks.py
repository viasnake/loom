import math
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from loom import (
    ActionMap,
    Column,
    GameApp,
    InputFrame,
    Label,
    Scene,
    StickBinding,
    UIRouter,
)


class StickTests(unittest.TestCase):
    def test_signed_bounds_clamp_radial_deadzone_and_inversion(self):
        stick = StickBinding(100, 101, deadzone=0.2)
        self.assertEqual(stick.normalize(-32768, 0), (-1, 0))
        self.assertEqual(stick.normalize(32767, 0), (1, 0))
        self.assertEqual(stick.normalize(100000, 0), (1, 0))
        self.assertEqual(stick.normalize(-(10**1000), 0), (-1, 0))
        self.assertEqual(stick.normalize(100, 100), (0, 0))
        x, y = stick.normalize(16384, 0)
        self.assertAlmostEqual(x, (16384 / 32767 - 0.2) / 0.8)
        self.assertEqual(y, 0)
        diagonal = stick.normalize(32767, 32767)
        self.assertAlmostEqual(math.hypot(*diagonal), 1)
        self.assertAlmostEqual(diagonal[0], diagonal[1])
        inverse = StickBinding(100, 101, invert_x=True, invert_y=True)
        self.assertEqual(
            inverse.normalize(-32768, 32767),
            tuple(-v for v in stick.normalize(-32768, 32767)),
        )

    def test_binding_validation(self):
        for kwargs in (
            {"x": True},
            {"x": -1},
            {"x": 101},
            {"deadzone": True},
            {"deadzone": 1},
            {"deadzone": -1},
            {"deadzone": float("nan")},
            {"deadzone": float("inf")},
            {"deadzone": "0"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                StickBinding(**({"x": 100, "y": 101} | kwargs))
        with self.assertRaises(TypeError):
            StickBinding(100, 101, invert_y=1)
        with self.assertRaises(ValueError):
            StickBinding(100, 101).normalize(1.5, 0)

    def test_shared_axes_polled_once_without_digital_poll(self):
        actions = ActionMap(
            {"fire": [1]},
            watched_keys=[2],
            sticks={"move": StickBinding(100, 101), "aim": StickBinding(100, 102)},
        )
        digital, axes = [], []
        frame = actions.sample(
            lambda key: digital.append(key) or False,
            axis_value=lambda key: axes.append(key) or 32767,
        )
        self.assertEqual(digital, [1, 2])
        self.assertEqual(axes, [100, 101, 102])
        self.assertFalse(frame.held | frame.pressed | frame.released)
        self.assertEqual(set(frame.sticks), {"move", "aim"})

    def test_collisions_rejected_atomically(self):
        binding = StickBinding(100, 101)
        for kwargs in (
            {"bindings": {"move": [1]}},
            {"bindings": {"fire": [100]}},
            {"bindings": {}, "watched_keys": [101]},
        ):
            with self.assertRaises(ValueError):
                ActionMap(sticks={"move": binding}, **kwargs)
        actions = ActionMap({"fire": [1]}, sticks={"move": binding})
        original = actions.bindings
        for replacement in ({"fire": [100]}, {"move": [1]}):
            with self.assertRaises(ValueError):
                actions.replace_bindings(replacement)
            self.assertIs(actions.bindings, original)
        for bad in ([], [("move", binding)]):
            with self.assertRaises(TypeError):
                ActionMap({}, sticks=bad)
        with self.assertRaises(TypeError):
            ActionMap({}, sticks={"move": (100, 101)})

    def test_snapshot_copies_vectors_and_without_removes_names(self):
        source = {"move": [0.5, 0.25]}
        frame = InputFrame(sticks=source)
        source["move"][0] = 0
        source["new"] = (0, 0)
        self.assertEqual(frame.sticks, {"move": (0.5, 0.25)})
        with self.assertRaises(TypeError):
            frame.sticks["move"] = (0, 0)
        self.assertEqual(frame.without({"move"}).sticks, {})
        self.assertIs(InputFrame().sticks, InputFrame().sticks)
        for value in (
            {"move": (1, 1)},
            {"move": (float("nan"), 0)},
            {"move": (True, 0)},
            {"": (0, 0)},
        ):
            with self.assertRaises(ValueError):
                InputFrame(sticks=value)
        with self.assertRaises(TypeError):
            InputFrame(sticks=[])

    def test_frame_hash_compatibility_and_vector_equality(self):
        self.assertEqual(hash(InputFrame()), hash(InputFrame()))
        first = InputFrame(sticks={"move": (0.5, 0)})
        equal = InputFrame(sticks={"move": [0.5, 0]})
        different = InputFrame(sticks={"move": (0, 0.5)})
        self.assertEqual(hash(first), hash(equal))
        self.assertEqual(len({first, equal}), 1)
        self.assertNotEqual(first, different)
        self.assertEqual(len({first, different}), 2)

    def test_cancel_notifies_stick_without_digital_release_and_blocks_until_neutral(
        self,
    ):
        actions = ActionMap({}, sticks={"move": StickBinding(100, 101)})
        raw = {100: 32767, 101: 32767}

        def sample():
            return actions.sample(lambda key: False, axis_value=raw.__getitem__)

        self.assertNotEqual(sample().sticks["move"], (0, 0))
        actions.cancel()
        frame = sample()
        self.assertEqual(frame.cancelled, {"move"})
        self.assertFalse(frame.held | frame.pressed | frame.released)
        self.assertEqual(frame.sticks["move"], (0, 0))
        raw[100] = 0
        self.assertEqual(sample().sticks["move"], (0, 0))
        actions.reset()
        self.assertEqual(sample().sticks["move"], (0, 0))
        raw[101] = 0
        self.assertEqual(sample().sticks["move"], (0, 0))
        raw[100] = 32767
        self.assertEqual(sample().sticks["move"], (1, 0))
        actions.reset()
        self.assertEqual(sample().sticks["move"], (1, 0))

    def test_rebind_cancels_sticks_but_equal_map_does_not(self):
        actions = ActionMap({"fire": [1]}, sticks={"move": StickBinding(100, 101)})

        def sample():
            return actions.sample(
                lambda key: True, axis_value=lambda key: 32767 if key == 100 else 0
            )

        sample()
        actions.replace_bindings({"fire": [1]})
        self.assertEqual(sample().sticks["move"], (1, 0))
        actions.replace_bindings({"fire": [2]})
        frame = sample()
        self.assertEqual(frame.cancelled, {"move", "fire"})
        self.assertEqual(frame.released, {"fire"})
        self.assertEqual(frame.sticks["move"], (0, 0))

    def test_invalid_axis_reader_does_not_mutate_previous_snapshot(self):
        actions = ActionMap({}, sticks={"move": StickBinding(100, 101)})
        frame = actions.sample(lambda key: False, axis_value=lambda key: 32767)
        with self.assertRaises(ValueError):
            actions.sample(lambda key: False)
        with self.assertRaises(ValueError):
            actions.sample(lambda key: False, axis_value=lambda key: float("nan"))
        actions.cancel()
        self.assertEqual(
            actions.sample(lambda key: False, axis_value=lambda key: 0).cancelled,
            {"move"},
        )
        self.assertNotEqual(frame.sticks["move"], (0, 0))


class StickRoutingTests(unittest.TestCase):
    def frame(self, vector):
        return InputFrame(sticks={"move": vector})

    def test_modal_cancels_once_and_requires_both_axes_neutral_after_close(self):
        panel = Column()
        router = UIRouter([panel])
        self.assertEqual(
            router.update(self.frame((0.5, 0.5))).remaining.sticks["move"], (0.5, 0.5)
        )
        panel.modal = True
        interrupted = router.update(self.frame((0.5, 0.5))).remaining
        self.assertEqual(interrupted.cancelled, {"move"})
        self.assertFalse(interrupted.released)
        self.assertEqual(interrupted.sticks["move"], (0, 0))
        self.assertFalse(router.update(self.frame((0.5, 0.5))).remaining.cancelled)
        panel.modal = False
        self.assertEqual(
            router.update(self.frame((0, 0.5))).remaining.sticks["move"], (0, 0)
        )
        self.assertEqual(
            router.update(self.frame((0, 0))).remaining.sticks["move"], (0, 0)
        )
        self.assertEqual(
            router.update(self.frame((1, 0))).remaining.sticks["move"], (1, 0)
        )

    def test_reset_and_callback_modal_open_close_gate_sticks(self):
        from loom import Button

        router = UIRouter()
        modal = Column(modal=True)
        opener = Column([Button("Open", lambda: router.add(modal))])
        router.add(opener)
        router.update(
            InputFrame(
                held=frozenset({"primary"}),
                pressed=frozenset({"primary"}),
                pointer=(10, 10),
                sticks={"move": (1, 0)},
            )
        )
        frame = router.update(
            InputFrame(
                released=frozenset({"primary"}),
                pointer=(10, 10),
                sticks={"move": (1, 0)},
            )
        ).remaining
        self.assertEqual(frame.sticks["move"], (0, 0))
        self.assertEqual(frame.cancelled, {"move"})
        router.remove(modal)
        self.assertEqual(
            router.update(self.frame((1, 0))).remaining.sticks["move"], (0, 0)
        )
        router.update(self.frame((0, 0)))
        router.update(self.frame((1, 0)))
        reset = router.update(self.frame((1, 0)), reset=True).remaining
        self.assertEqual(reset.cancelled, {"move"})
        self.assertFalse(reset.released)

    def test_nonmodal_hover_preserves_movement(self):
        router = UIRouter([Column()])
        self.assertEqual(
            router.update(self.frame((1, 0))).remaining.sticks["move"], (1, 0)
        )


class StickRuntimeTests(unittest.TestCase):
    def test_runtime_routes_only_registered_axes_through_btnv(self):
        seen, digital, axes = [], [], []

        class Probe(Scene):
            def update(self, frame, dt):
                seen.append(frame)

        engine = SimpleNamespace(
            KEY_NONE=0,
            init=lambda *a, **kw: None,
            mouse=lambda visible: None,
            mouse_x=0,
            mouse_y=0,
            mouse_wheel=0,
            Image=lambda w, h: (w, h),
            btn=lambda key: digital.append(key) or False,
            btnv=lambda key: axes.append(key) or 32767,
            run=lambda update, draw: update(),
        )
        app = GameApp(
            "stick",
            Probe(),
            bindings={"fire": [1]},
            sticks={"move": StickBinding(100, 101)},
        )
        with patch.dict(sys.modules, {"pyxel": engine}):
            app.run(headless=True)
        self.assertEqual(digital, [1])
        self.assertEqual(axes, [100, 101])
        self.assertIn("move", seen[0].sticks)
        with self.assertRaises(ValueError):
            app.request_bindings({"bad": [100]})

    def test_runtime_rejects_nonmapping_empty_bindings(self):
        for bindings in ([], ""):
            with self.assertRaises(TypeError):
                GameApp("bad", Scene(), bindings=bindings)


class StickAliasTests(unittest.TestCase):
    def test_explicit_pointer_alias_is_blocked_until_neutral(self):
        router = UIRouter([Column([Label("panel")])], pointer_actions={"move"})
        frame = InputFrame(pointer=(10, 10), sticks={"move": (1, 0)})
        self.assertEqual(router.update(frame).remaining.sticks["move"], (0, 0))
        outside = InputFrame(pointer=(999, 999), sticks={"move": (1, 0)})
        self.assertEqual(router.update(outside).remaining.sticks["move"], (0, 0))
        router.update(InputFrame(pointer=(999, 999), sticks={"move": (0, 0)}))
        self.assertEqual(router.update(outside).remaining.sticks["move"], (1, 0))
