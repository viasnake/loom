import unittest

from loom.ui import Button, Column, Label, Rect, Theme, Typography, UIInput
from loom.input import InputFrame
from loom.text import FontCatalog


class RecordingCanvas:
    def __init__(self):
        self.calls = []

    def rect(self, *args):
        self.calls.append(("rect", args))

    def text(self, *args):
        self.calls.append(("text", args))


class UITests(unittest.TestCase):
    def setUp(self):
        self.clicked = []
        self.a = Button("A", lambda: self.clicked.append("a"))
        self.b = Button("B", lambda: self.clicked.append("b"))
        self.panel = Column([self.a, self.b], x=10, y=10, width=100)
        self.panel.layout()

    def point(self, widget, **kwargs):
        return UIInput(widget.rect.x + 1, widget.rect.y + 1, **kwargs)

    def test_rect_half_open_bounds(self):
        rect = Rect(0, 0, 10, 10)
        self.assertTrue(rect.contains(0, 0))
        self.assertFalse(rect.contains(10, 5))
        self.assertFalse(rect.contains(5, 10))
        self.assertFalse(rect.contains(None, None))

    def test_press_does_not_activate_release_does(self):
        self.assertTrue(
            self.panel.update(self.point(self.a, pointer_pressed=True)).pointer_consumed
        )
        self.assertEqual(self.clicked, [])
        self.panel.update(self.point(self.a, pointer_released=True))
        self.assertEqual(self.clicked, ["a"])

    def test_release_without_owned_press_does_not_activate(self):
        self.panel.update(self.point(self.a, pointer_released=True))
        self.assertEqual(self.clicked, [])

    def test_drag_between_buttons_does_not_activate_either(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.update(self.point(self.b, pointer_released=True))
        self.assertEqual(self.clicked, [])

    def test_owned_release_outside_consumed(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        result = self.panel.update(UIInput(999, 999, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertFalse(self.panel.update(UIInput(999, 999)).pointer_consumed)
        self.assertEqual(self.clicked, [])

    def test_capture_cancelled_by_focus_reset(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.update(UIInput(reset=True))
        self.panel.update(self.point(self.a, pointer_released=True))
        self.assertEqual(self.clicked, [])

    def test_disable_during_press_does_not_activate_or_leak(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.a.enabled = False
        result = self.panel.update(UIInput(999, 999, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertEqual(self.clicked, [])

    def test_remove_during_press_does_not_leak_release(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.remove(self.a)
        self.assertTrue(
            self.panel.update(UIInput(999, 999, pointer_released=True)).pointer_consumed
        )
        self.assertEqual(self.clicked, [])

    def test_tab_navigation_skips_disabled_and_wraps(self):
        self.b.enabled = False
        self.assertTrue(self.panel.update(UIInput(next_focus=True)).keyboard_consumed)
        self.assertIs(self.panel.focused, self.a)
        self.panel.update(UIInput(next_focus=True))
        self.assertIs(self.panel.focused, self.a)
        self.panel.update(UIInput(confirm=True))
        self.assertEqual(self.clicked, ["a"])
        self.b.enabled = True
        self.panel.update(UIInput(previous_focus=True))
        self.assertIs(self.panel.focused, self.b)

    def test_reverse_focus_from_none_chooses_last(self):
        self.panel.update(UIInput(previous_focus=True))
        self.assertIs(self.panel.focused, self.b)

    def test_hidden_focus_does_not_activate(self):
        self.panel.update(UIInput(next_focus=True))
        self.a.visible = False
        self.panel.update(UIInput(confirm=True))
        self.assertEqual(self.clicked, [])
        self.assertIsNone(self.panel.focused)

    def test_click_and_confirm_same_frame_activates_once(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.update(self.point(self.a, pointer_released=True, confirm=True))
        self.assertEqual(self.clicked, ["a"])

    def test_confirm_during_pointer_press_cannot_activate_again_on_release(self):
        self.panel.update(self.point(self.a, pointer_pressed=True, confirm=True))
        self.assertEqual(self.clicked, ["a"])
        result = self.panel.update(self.point(self.a, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertEqual(self.clicked, ["a"])

    def test_modal_cancel_consumes_closing_frame(self):
        closed = []
        panel = Column([], modal=True, on_cancel=lambda: closed.append(True))
        result = panel.update(UIInput(999, 999, cancel=True, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertTrue(result.keyboard_consumed)
        self.assertTrue(result.cancelled)
        self.assertEqual(closed, [True])

    def test_cancel_prevents_confirm_and_click(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.update(
            self.point(self.a, pointer_released=True, cancel=True, confirm=True)
        )
        self.assertEqual(self.clicked, [])

    def test_cancel_during_drag_does_not_leak_later_release(self):
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.update(UIInput(cancel=True))
        result = self.panel.update(UIInput(999, 999, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertEqual(self.clicked, [])
        self.assertFalse(self.panel.update(UIInput(999, 999)).pointer_consumed)

    def test_callback_cannot_change_modal_consumption_of_current_frame(self):
        self.panel.modal = True
        self.a.on_click = lambda: setattr(self.panel, "modal", False)
        self.panel.update(self.point(self.a, pointer_pressed=True))
        result = self.panel.update(self.point(self.a, pointer_released=True))
        self.assertTrue(result.keyboard_consumed)
        self.assertTrue(result.pointer_consumed)
        self.assertFalse(self.panel.update(UIInput(999, 999)).consumed)

    def test_layout_is_cached_and_invalidation_is_explicit(self):
        count = self.panel.layout_count
        canvas = RecordingCanvas()
        for _ in range(10):
            self.panel.update(UIInput())
            self.panel.draw(canvas)
        self.assertEqual(self.panel.layout_count, count)
        self.a.height = 25
        self.panel.layout()
        self.assertEqual(self.panel.layout_count, count + 1)
        self.assertEqual(self.b.rect.y, 43)
        self.a.visible = False
        self.panel.layout()
        self.assertEqual(self.b.rect.y, 14)
        self.panel.configure(x=20, width=200)
        self.panel.layout()
        self.assertEqual(self.b.rect.x, 24)
        self.assertEqual(self.b.rect.width, 192)

    def test_callback_can_remove_its_button(self):
        self.a.on_click = lambda: self.panel.remove(self.a)
        self.panel.update(self.point(self.a, pointer_pressed=True))
        self.panel.update(self.point(self.a, pointer_released=True))
        self.assertNotIn(self.a, self.panel.children)
        self.panel.draw(RecordingCanvas())

    def test_single_owner(self):
        with self.assertRaises(ValueError):
            Column([self.a])
        self.panel.remove(self.a)
        self.assertEqual(Column([self.a]).children, (self.a,))

    def test_failed_constructor_does_not_take_partial_ownership(self):
        fresh = Label("Fresh")
        with self.assertRaises(ValueError):
            Column([fresh, self.a])
        self.assertEqual(Column([fresh]).children, (fresh,))

    def test_duplicate_child_rejected_without_taking_ownership(self):
        fresh = Label("Fresh")
        with self.assertRaises(ValueError):
            Column([fresh, fresh])
        self.assertEqual(Column([fresh]).children, (fresh,))

    def test_label_and_panel_use_theme(self):
        canvas = RecordingCanvas()
        panel = Column([Label("Title")], theme=Theme(panel=2, text=3))
        panel.draw(canvas)
        self.assertEqual(canvas.calls[0][-1][-1], 2)
        self.assertEqual(canvas.calls[1], ("text", (4, 4, "Title", 3)))

    def test_invalid_geometry(self):
        with self.assertRaises(ValueError):
            Column(width=8, padding=4)
        with self.assertRaises(ValueError):
            self.a.height = 0
        with self.assertRaises(ValueError):
            self.panel.configure(gap=-1)


class TypographyTests(unittest.TestCase):
    def setUp(self):
        self.fonts = FontCatalog()
        self.face = type("Face", (), {"text_width": lambda self, s: len(s) * 18})()
        self.fonts.register("body", self.face, line_height=18)
        self.typography = Typography(self.fonts, font="body")

    def test_auto_heights_match_font_and_multiline(self):
        label = Label("日本語\n設定")
        button = Button("始める", lambda: None)
        panel = Column([label, button], typography=self.typography)
        panel.layout()
        self.assertEqual(label.rect.height, 36)
        self.assertEqual(button.rect.height, 26)
        # Hit-testing uses measured geometry before any draw call.
        result = panel.update(
            UIInput(button.rect.x + 1, button.rect.y + 24, pointer_pressed=True)
        )
        self.assertTrue(result.pointer_consumed)
        self.assertIs(panel.focused, button)

    def test_expanded_button_bottom_activates_but_outside_does_not(self):
        clicked = []
        button = Button("開始", lambda: clicked.append(True))
        panel = Column([button], typography=self.typography)
        panel.layout()
        x, y = button.rect.x + 1, button.rect.y + 24
        panel.update(UIInput(x, y, pointer_pressed=True))
        panel.update(UIInput(x, y, pointer_released=True))
        self.assertEqual(clicked, [True])
        bottom = button.rect.y + button.rect.height
        panel.update(UIInput(x, bottom, pointer_pressed=True))
        panel.update(UIInput(x, bottom, pointer_released=True))
        self.assertEqual(clicked, [True])

    def test_replacing_catalog_with_same_revision_relayouts(self):
        label = Label("日本語")
        panel = Column([label], typography=self.typography)
        panel.layout()
        other = FontCatalog()
        other.register("body", self.face, line_height=24)
        self.assertEqual(other.revision, self.fonts.revision)
        panel.typography = Typography(other, font="body")
        panel.layout()
        self.assertEqual(label.rect.height, 24)
        self.assertEqual(panel.layout_count, 2)

    def test_minimum_height_button_centers_default_font(self):
        canvas = RecordingCanvas()
        button = Button("B", lambda: None)
        panel = Column([button])
        panel.draw(canvas)
        self.assertIn(("text", (8, 11, "B", 7)), canvas.calls)

    def test_explicit_height_is_not_enlarged(self):
        label = Label("日本語", height=2)
        panel = Column([label], typography=self.typography)
        panel.layout()
        self.assertEqual(label.rect.height, 2)
        label.height = None
        panel.layout()
        self.assertEqual(label.rect.height, 18)

    def test_text_and_registration_invalidate_once(self):
        label = Label("")
        panel = Column([label], typography=self.typography)
        panel.layout()
        self.assertEqual(label.rect.height, 18)
        panel.layout()
        self.assertEqual(panel.layout_count, 1)
        label.text = "一\n二"
        panel.layout()
        self.assertEqual(label.rect.height, 36)
        label.text = "一\n二"
        panel.layout()
        self.assertEqual(panel.layout_count, 2)
        self.fonts.register("body", self.face, line_height=22)
        panel.layout()
        self.assertEqual(label.rect.height, 44)
        self.assertEqual(panel.layout_count, 3)
        self.fonts.clear_cache()
        panel.layout()
        self.assertEqual(panel.layout_count, 3)

    def test_typography_replacement_and_default_minimums(self):
        label, button = Label("A"), Button("B", lambda: None)
        panel = Column([label, button])
        panel.layout()
        self.assertEqual((label.rect.height, button.rect.height), (12, 20))
        panel.typography = self.typography
        panel.layout()
        self.assertEqual((label.rect.height, button.rect.height), (18, 26))
        panel.typography = None
        panel.layout()
        self.assertEqual((label.rect.height, button.rect.height), (12, 20))

    def test_draw_uses_registered_font_and_line_spacing(self):
        class FontCanvas(RecordingCanvas):
            def text(self, *args, font=None):
                self.calls.append(("text", args, font))

        canvas = FontCanvas()
        label = Label("廃墟\n街")
        button = Button("開始", lambda: None)
        panel = Column([label, button], typography=self.typography)
        panel.draw(canvas)
        text_calls = [call for call in canvas.calls if call[0] == "text"]
        self.assertEqual(
            text_calls,
            [
                ("text", (4, 4, "廃墟", 7), self.face),
                ("text", (4, 22, "街", 7), self.face),
                ("text", (8, button.rect.y + 4, "開始", 7), self.face),
            ],
        )
        panel.draw(canvas)
        self.assertEqual(panel.layout_count, 1)

    def test_frame_bridge_maps_edges_not_held_or_world_pointer(self):
        actions = frozenset({"primary", "confirm", "cancel", "next", "previous"})
        frame = InputFrame(
            held=actions,
            pressed=actions,
            released=actions,
            pointer=(12, 34),
            world_pointer=(1, 2),
        )
        ui = UIInput.from_frame(frame, reset=True)
        self.assertEqual(ui, UIInput(12, 34, True, True, True, True, True, True, True))
        held = UIInput.from_frame(InputFrame(held=actions, pointer=(12, 34)))
        self.assertEqual(held, UIInput(12, 34))


class ScrollTests(unittest.TestCase):
    def setUp(self):
        self.clicked = []
        self.buttons = [
            Button(str(i), lambda i=i: self.clicked.append(i)) for i in range(5)
        ]
        self.panel = Column(self.buttons, width=100, viewport_height=56)
        self.panel.layout()

    def test_scroll_clamps_and_ignores_wheel_outside(self):
        self.panel.update(UIInput(10, 10, scroll_y=24))
        self.assertEqual(self.panel.scroll_offset, 24)
        self.assertEqual(self.buttons[0].rect.y, -20)
        self.panel.update(UIInput(101, 10, scroll_y=24))
        self.assertEqual(self.panel.scroll_offset, 24)
        self.panel.scroll_offset = 10000
        self.assertEqual(self.panel.scroll_offset, 68)
        self.panel.scroll_offset = -5
        self.assertEqual(self.panel.scroll_offset, 0)
        self.assertEqual(self.panel.layout_count, 1)

    def test_clipped_part_cannot_hover_or_activate(self):
        # Third button begins at y=52, exactly at the inner viewport bottom.
        self.panel.update(UIInput(10, 53, pointer_pressed=True))
        self.panel.update(UIInput(10, 53, pointer_released=True))
        self.assertEqual(self.clicked, [])
        self.assertIsNone(self.panel.focused)
        self.panel.update(UIInput(10, 30, pointer_pressed=True))
        self.panel.update(UIInput(10, 30, pointer_released=True))
        self.assertEqual(self.clicked, [1])

    def test_scroll_cancels_click_but_owns_release(self):
        self.panel.update(UIInput(10, 10, pointer_pressed=True))
        self.panel.update(UIInput(10, 10, scroll_y=24))
        result = self.panel.update(UIInput(200, 200, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertEqual(self.clicked, [])
        self.assertFalse(self.panel.update(UIInput(200, 200)).pointer_consumed)

    def test_tab_reveals_focus_but_idle_does_not_override_wheel(self):
        for _ in range(3):
            self.panel.update(UIInput(next_focus=True))
        self.assertIs(self.panel.focused, self.buttons[2])
        self.assertEqual(self.panel.scroll_offset, 20)
        self.panel.update(UIInput(10, 10, scroll_y=48))
        self.panel.update(UIInput())
        self.assertEqual(self.panel.scroll_offset, 68)
        self.panel.update(UIInput(previous_focus=True))
        self.assertIs(self.panel.focused, self.buttons[1])
        self.assertEqual(self.buttons[1].rect.y, 4)

    def test_confirm_reveals_focus_after_manual_scroll(self):
        self.panel.update(UIInput(next_focus=True))
        self.panel.update(UIInput(10, 10, scroll_y=68))
        self.panel.update(UIInput())
        self.assertEqual(self.panel.scroll_offset, 68)
        self.panel.update(UIInput(confirm=True))
        self.assertEqual(self.panel.scroll_offset, 0)
        self.assertEqual(self.clicked, [0])

    def test_oversized_focus_aligns_top(self):
        self.buttons[1].height = 80
        self.panel.update(UIInput(previous_focus=True))
        self.panel.update(UIInput(next_focus=True))
        self.panel.update(UIInput(next_focus=True))
        self.assertIs(self.panel.focused, self.buttons[1])
        self.assertEqual(self.buttons[1].rect.y, 4)

    def test_remove_and_hide_clamp_offset(self):
        self.panel.scroll_offset = 1000
        for button in self.buttons[2:]:
            self.panel.remove(button)
        self.assertEqual(self.panel.scroll_offset, 0)
        self.assertEqual(self.panel.rect.height, 56)
        self.buttons[1].visible = False
        self.panel.layout()
        self.assertEqual(self.panel.scroll_offset, 0)

    def test_finite_panel_requires_managed_clip(self):
        canvas = RecordingCanvas()
        with self.assertRaisesRegex(TypeError, "ClippingCanvas"):
            self.panel.draw(canvas)
        self.assertEqual(canvas.calls, [])

    def test_draw_culls_outside_and_closes_clip_on_exception(self):
        from contextlib import contextmanager

        class ClipCanvas(RecordingCanvas):
            active = False

            @contextmanager
            def clipped(self, rect):
                self.active = True
                self.clip_rect = rect
                try:
                    yield
                finally:
                    self.active = False

        canvas = ClipCanvas()
        self.panel.draw(canvas)
        self.assertEqual(canvas.clip_rect, Rect(4, 4, 92, 48))
        self.assertEqual(
            [call[1][2] for call in canvas.calls if call[0] == "text"], ["0", "1"]
        )
        self.assertFalse(canvas.active)

        def fail(*args, **kwargs):
            raise RuntimeError("draw")

        self.buttons[0].draw = fail
        with self.assertRaises(RuntimeError):
            self.panel.draw(canvas)
        self.assertFalse(canvas.active)

    def test_font_shrink_clamps_offset(self):
        fonts = FontCatalog()
        fonts.register("body", line_height=30)
        panel = Column(
            [Label("A"), Label("B")],
            viewport_height=40,
            typography=Typography(fonts, "body"),
        )
        panel.scroll_offset = 1000
        self.assertEqual(panel.scroll_offset, 32)
        fonts.register("body", line_height=6)
        self.assertEqual(panel.scroll_offset, 0)

    def test_wheel_bridge_direction_rounding_and_step_validation(self):
        frame = InputFrame(wheel=-1)
        self.assertEqual(UIInput.from_frame(frame).scroll_y, 24)
        self.assertEqual(
            UIInput.from_frame(InputFrame(wheel=0.5), scroll_step=20).scroll_y, -10
        )
        for step in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                UIInput.from_frame(frame, scroll_step=step)

    def test_viewport_validation(self):
        for height in (True, False, 40.5, 40.0):
            with self.assertRaises(TypeError):
                Column(viewport_height=height)
        with self.assertRaises(ValueError):
            Column(viewport_height=8)
        with self.assertRaises(ValueError):
            self.panel.configure(padding=28)
        with self.assertRaises(TypeError):
            self.panel.scroll_offset = 1.5


if __name__ == "__main__":
    unittest.main()


class ScrollBoundaryTests(unittest.TestCase):
    def test_inner_right_and_bottom_edges_are_excluded(self):
        clicked = []
        panel = Column(
            [Button("Tall", lambda: clicked.append(True), height=40)],
            width=100,
            viewport_height=30,
            padding=4,
        )
        for x, y in ((96, 10), (10, 26)):
            panel.update(UIInput(x, y, pointer_pressed=True))
            panel.update(UIInput(x, y, pointer_released=True))
        self.assertEqual(clicked, [])
        panel.update(UIInput(95, 25, pointer_pressed=True))
        panel.update(UIInput(95, 25, pointer_released=True))
        self.assertEqual(clicked, [True])

    def test_programmatic_scroll_cancels_click_but_owns_release(self):
        clicked = []
        panel = Column(
            [Button(str(i), lambda i=i: clicked.append(i)) for i in range(10)],
            viewport_height=40,
        )
        panel.update(UIInput(6, 6, pointer_pressed=True))
        panel.scroll_offset = 24
        released = panel.update(UIInput(999, 999, pointer_released=True))
        self.assertTrue(released.pointer_consumed)
        self.assertEqual(clicked, [])
        self.assertFalse(panel.update(UIInput(999, 999)).pointer_consumed)
