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
