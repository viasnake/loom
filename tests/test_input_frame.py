import unittest

from loom import InputFrame, UIRouter


class InputFrameOwnershipTests(unittest.TestCase):
    def test_mutable_buffers_cannot_rewrite_a_published_frame(self):
        sources = {
            "held": {"move"},
            "pressed": {"fire"},
            "released": {"jump"},
            "cancelled": {"dash"},
        }
        pointer = [10, 20]
        world = [30, 40]
        frame = InputFrame(**sources, pointer=pointer, world_pointer=world)
        for source in sources.values():
            source.clear()
            source.add("replacement")
        pointer[:] = world[:] = [999, 999]
        self.assertEqual(frame.held, frozenset({"move"}))
        self.assertEqual(frame.pressed, frozenset({"fire"}))
        self.assertEqual(frame.released, frozenset({"jump"}))
        self.assertEqual(frame.cancelled, frozenset({"dash"}))
        self.assertEqual(frame.pointer, (10, 20))
        self.assertEqual(frame.world_pointer, (30, 40))
        self.assertIsInstance(hash(frame), int)

    def test_routing_uses_original_press_after_source_is_reused(self):
        held = {"fire"}
        pressed = {"fire"}
        frame = InputFrame(held=held, pressed=pressed)
        held.clear()
        pressed.clear()
        router = UIRouter()
        result = router.update(frame).remaining
        self.assertEqual(result.held, {"fire"})
        self.assertEqual(result.pressed, {"fire"})
        result = router.update(InputFrame(released={"fire"})).remaining
        self.assertEqual(result.released, {"fire"})

    def test_existing_immutable_buffers_are_reused(self):
        actions = frozenset({"fire"})
        point = (2, 3)
        frame = InputFrame(actions, actions, actions, point, point, cancelled=actions)
        for name in ("held", "pressed", "released", "cancelled"):
            self.assertIs(getattr(frame, name), actions)
        self.assertIs(frame.pointer, point)
        self.assertIs(frame.world_pointer, point)

    def test_without_does_not_share_mutable_actions(self):
        source = {"fire", "move"}
        frame = InputFrame(held=source)
        remaining = frame.without({"fire"})
        source.clear()
        self.assertEqual(frame.held, {"fire", "move"})
        self.assertEqual(remaining.held, {"move"})
        self.assertIsNone(remaining.world_pointer)

    def test_bare_text_and_mappings_are_not_action_collections(self):
        for name in ("held", "pressed", "released", "cancelled"):
            for value in ("fire", b"fire", bytearray(b"fire"), {"fire": True}):
                with self.subTest(name=name, value=value), self.assertRaises(TypeError):
                    InputFrame(**{name: value})

    def test_empty_filter_reuses_snapshot_without_losing_input(self):
        sticks = {"move": [0.5, -0.25]}
        frame = InputFrame(
            held={"confirm"},
            pressed={"confirm"},
            released={"jump"},
            cancelled={"jump"},
            pointer=[10, 20],
            world_pointer=[30, 40],
            wheel=-2,
            sticks=sticks,
        )
        actions = set()
        for _ in range(1000):
            self.assertIs(frame.without(actions), frame)
        self.assertIs(frame.without(frozenset()), frame)
        actions.add("confirm")
        sticks["move"][:] = [0, 0]
        self.assertEqual(frame.held, {"confirm"})
        self.assertEqual(frame.sticks["move"], (0.5, -0.25))
        self.assertEqual(
            (frame.pointer, frame.world_pointer, frame.wheel), ((10, 20), (30, 40), -2)
        )
        self.assertEqual(frame.released, {"jump"})
        self.assertEqual(frame.cancelled, {"jump"})
        with self.assertRaises(TypeError):
            frame.sticks["move"] = (0, 0)

    def test_nonempty_filter_removes_each_channel_and_keeps_coordinates(self):
        frame = InputFrame(
            held={"keep", "drop"},
            pressed={"keep", "drop"},
            released={"keep", "drop"},
            cancelled={"keep", "drop"},
            pointer=(10, 20),
            world_pointer=(30, 40),
            wheel=3,
            sticks={"keep": (0.5, 0), "drop": (0, 1)},
        )
        result = frame.without({"drop"})
        self.assertIsNot(result, frame)
        for name in ("held", "pressed", "released", "cancelled"):
            self.assertEqual(getattr(result, name), {"keep"})
            self.assertEqual(getattr(frame, name), {"keep", "drop"})
        self.assertEqual(dict(result.sticks), {"keep": (0.5, 0)})
        self.assertEqual(
            (result.pointer, result.world_pointer, result.wheel),
            (frame.pointer, frame.world_pointer, frame.wheel),
        )

    def test_empty_filter_preserves_repeat_navigation_and_release(self):
        from loom import ActionRepeat, Button, Column

        buttons = [Button(str(i), lambda: None) for i in range(3)]
        panel = Column(buttons, width=80)
        router = UIRouter([panel], repeat=ActionRepeat({"next"}, delay=0.2))
        router.update(InputFrame(held={"next"}, pressed={"next"}), dt=0)
        self.assertIs(panel.focused, buttons[0])
        router.update(InputFrame(held={"next"}), dt=0.2)
        self.assertIs(panel.focused, buttons[1])
        result = router.update(InputFrame(released={"next"}), dt=0.2)
        self.assertNotIn("next", result.remaining.released)
        router.update(InputFrame(), dt=1)
        self.assertIs(panel.focused, buttons[1])

    def test_subclass_filter_keeps_base_snapshot_contract(self):
        class CustomFrame(InputFrame):
            pass

        frame = CustomFrame(held={"next"})
        result = frame.without(set())
        self.assertIs(type(result), InputFrame)
        self.assertIsNot(result, frame)
        self.assertEqual(result.held, frame.held)

    def test_empty_invalid_filter_still_raises(self):
        for actions in (None, [], {}, ""):
            with self.subTest(actions=actions), self.assertRaises(TypeError):
                InputFrame().without(actions)

    def test_set_subclass_retains_subtraction_without_truthiness(self):
        class Filter(set):
            def __bool__(self):
                raise AssertionError("must not test filter truthiness")

        frame = InputFrame(held={"keep"})
        result = frame.without(Filter())
        self.assertIsNot(result, frame)
        self.assertEqual(result, frame)
