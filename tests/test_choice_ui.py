import unittest

from loom import Button, Choice, Column, UIInput
from loom.ui import Theme


class Canvas:
    def __init__(self):
        self.texts = []

    def rect(self, *args):
        pass

    def text(self, *args):
        self.texts.append(args)


class ChoiceTests(unittest.TestCase):
    def setUp(self):
        self.changes = []
        self.choice = Choice(
            "Mode", ["Easy", "Normal", "Hard"], on_change=self.changes.append
        )
        self.panel = Column([self.choice])

    def test_validation_and_snapshot(self):
        for options, error in (([], ValueError), ("abc", TypeError), ([1], TypeError)):
            with self.assertRaises(error):
                Choice("Mode", options)
        for index, error in (
            (True, TypeError),
            (1.0, TypeError),
            (-1, ValueError),
            (3, ValueError),
        ):
            with self.assertRaises(error):
                self.choice.index = index
            with self.assertRaises(error):
                Choice("Mode", self.choice.options, index)
        labels = ["A", "B"]
        choice = Choice("Mode", labels)
        labels[0] = "C"
        labels.append("D")
        self.assertEqual(choice.options, ("A", "B"))
        with self.assertRaises(AttributeError):
            choice.options = ("Other",)

    def test_keyboard_cycles_and_consumes_at_both_boundaries(self):
        self.assertFalse(self.panel.update(UIInput(increment=True)).keyboard_consumed)
        self.panel.update(UIInput(next_focus=True))
        for flags, expected in (
            ({"decrement": True}, 2),
            ({"increment": True}, 0),
            ({"confirm": True}, 1),
        ):
            result = self.panel.update(UIInput(**flags))
            self.assertTrue(result.keyboard_consumed)
            self.assertEqual(self.choice.index, expected)
        result = self.panel.update(UIInput(increment=True, decrement=True))
        self.assertTrue(result.keyboard_consumed)
        self.assertEqual(self.changes, [2, 0, 1])

    def test_click_is_not_drag_and_combined_edges_notify_once(self):
        self.panel.update(UIInput(10, 10, pointer_pressed=True))
        self.panel.update(UIInput(20, 10))
        self.assertEqual(self.changes, [])
        result = self.panel.update(
            UIInput(10, 10, pointer_released=True, confirm=True, increment=True)
        )
        self.assertTrue(result.pointer_consumed)
        self.assertTrue(result.keyboard_consumed)
        self.assertEqual(self.changes, [1])
        self.panel.update(UIInput(10, 10, pointer_released=True))
        self.assertEqual(self.changes, [1])

    def test_outside_release_and_interruptions_do_not_activate(self):
        for interruption in ("outside", "disable", "hide", "remove", "cancel", "reset"):
            with self.subTest(interruption=interruption):
                changes = []
                choice = Choice("Mode", ("A", "B"), on_change=changes.append)
                panel = Column([choice])
                panel.update(UIInput(10, 10, pointer_pressed=True))
                if interruption == "disable":
                    choice.enabled = False
                elif interruption == "hide":
                    choice.visible = False
                elif interruption == "remove":
                    panel.remove(choice)
                elif interruption in ("cancel", "reset"):
                    panel.update(UIInput(**{interruption: True}))
                result = panel.update(UIInput(900, 900, pointer_released=True))
                self.assertEqual(changes, [])
                if interruption != "reset":
                    self.assertTrue(result.pointer_consumed)

    def test_disabled_hidden_skip_focus_and_programmatic_changes_work(self):
        other = Button("OK", lambda: None)
        self.panel.add(other)
        self.choice.enabled = False
        self.panel.update(UIInput(next_focus=True))
        self.assertIs(self.panel.focused, other)
        self.assertFalse(self.panel.update(UIInput(increment=True)).keyboard_consumed)
        self.choice.index = 1
        self.assertEqual(self.changes, [1])
        self.choice.enabled = True
        self.choice.visible = False
        self.panel.update(UIInput(next_focus=True))
        self.assertIs(self.panel.focused, other)

    def test_silent_initial_same_index_and_single_option(self):
        choice = Choice("Only", ("A",), on_change=self.changes.append)
        panel = Column([choice])
        panel.update(UIInput(next_focus=True))
        for flags in ({"confirm": True}, {"increment": True}, {"decrement": True}):
            self.assertTrue(panel.update(UIInput(**flags)).keyboard_consumed)
        self.choice.index = 0
        self.assertEqual(self.changes, [])

    def test_dynamic_text_selection_retained_layout_and_callback_state(self):
        choice = Choice("Mode", ("A", "B\nC\nD"))
        panel = Column([choice])
        canvas = Canvas()
        panel.draw(canvas)
        self.assertEqual(choice.rect.height, 20)
        count = panel.layout_count
        panel.draw(canvas)
        self.assertEqual(panel.layout_count, count)
        seen = []
        choice.on_change = lambda index: seen.append(
            (index, choice.option, panel.rect.height)
        )
        choice.index = 1
        self.assertEqual(seen, [(1, "B\nC\nD", 34)])
        panel.draw(canvas)
        self.assertEqual(canvas.texts[-1][2], "Mode: < B\nC\nD >")
        self.assertEqual(choice.rect.height, 26)
        choice.text = "New\nMode"
        panel.layout()
        self.assertEqual(choice.rect.height, 32)
        choice.height = 10
        panel.layout()
        self.assertEqual(choice.rect.height, 10)
        choice.enabled = False
        panel.draw(canvas)
        self.assertEqual(canvas.texts[-1][-1], Theme().disabled)

    def test_callback_can_remove_control_without_releasing_to_game(self):
        self.choice.on_change = lambda index: self.panel.remove(self.choice)
        self.panel.update(UIInput(10, 10, pointer_pressed=True))
        result = self.panel.update(UIInput(increment=True))
        self.assertTrue(result.keyboard_consumed)
        self.assertEqual(self.panel.children, ())
        self.assertTrue(
            self.panel.update(UIInput(900, 900, pointer_released=True)).pointer_consumed
        )

    def test_router_removes_adjustment_edges_from_game(self):
        from loom import InputFrame, UIRouter

        router = UIRouter([self.panel])
        router.update(InputFrame(pressed=frozenset({"next"})))
        result = router.update(InputFrame(pressed=frozenset({"decrement", "fire"})))
        self.assertNotIn("decrement", result.remaining.pressed)
        self.assertIn("fire", result.remaining.pressed)
        self.assertEqual(self.choice.index, 2)

    def test_typography_revision_and_scrolled_focus(self):
        from loom import FontCatalog, Label, Typography

        self.panel.remove(self.choice)
        fonts = FontCatalog()
        fonts.register("body", line_height=18)
        panel = Column(
            [Label("Heading", height=40), self.choice],
            typography=Typography(fonts, "body"),
            viewport_height=40,
        )
        panel.layout()
        self.assertEqual(self.choice.rect.height, 26)
        panel.update(UIInput(next_focus=True))
        self.assertIs(panel.focused, self.choice)
        self.assertGreater(panel.scroll_offset, 0)
        self.assertEqual(self.choice.rect.y + self.choice.rect.height, 36)
        fonts.register("body", line_height=24)
        panel.update(UIInput(increment=True))
        self.assertEqual(self.choice.rect.height, 32)
        self.assertEqual(self.choice.rect.y, 4)
        self.assertEqual(self.changes, [1])
