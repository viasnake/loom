import unittest

from loom.ui import Button, Column, Label, Rect, Theme, UIInput


class RecordingCanvas:
    def __init__(self):
        self.calls = []

    def rect(self, *args):
        self.calls.append(('rect', args))

    def text(self, *args):
        self.calls.append(('text', args))


class UITests(unittest.TestCase):
    def setUp(self):
        self.clicked = []
        self.a = Button('A', lambda: self.clicked.append('a'))
        self.b = Button('B', lambda: self.clicked.append('b'))
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
        self.assertTrue(self.panel.update(self.point(self.a, pointer_pressed=True)).pointer_consumed)
        self.assertEqual(self.clicked, [])
        self.panel.update(self.point(self.a, pointer_released=True))
        self.assertEqual(self.clicked, ['a'])

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
        self.assertTrue(self.panel.update(UIInput(999, 999, pointer_released=True)).pointer_consumed)
        self.assertEqual(self.clicked, [])

    def test_tab_navigation_skips_disabled_and_wraps(self):
        self.b.enabled = False
        self.assertTrue(self.panel.update(UIInput(next_focus=True)).keyboard_consumed)
        self.assertIs(self.panel.focused, self.a)
        self.panel.update(UIInput(next_focus=True))
        self.assertIs(self.panel.focused, self.a)
        self.panel.update(UIInput(confirm=True))
        self.assertEqual(self.clicked, ['a'])
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
        self.assertEqual(self.clicked, ['a'])

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
        self.panel.update(self.point(self.a, pointer_released=True, cancel=True, confirm=True))
        self.assertEqual(self.clicked, [])

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

    def test_label_and_panel_use_theme(self):
        canvas = RecordingCanvas()
        panel = Column([Label('Title')], theme=Theme(panel=2, text=3))
        panel.draw(canvas)
        self.assertEqual(canvas.calls[0][-1][-1], 2)
        self.assertEqual(canvas.calls[1], ('text', (4, 4, 'Title', 3)))

    def test_invalid_geometry(self):
        with self.assertRaises(ValueError):
            Column(width=8, padding=4)
        with self.assertRaises(ValueError):
            self.a.height = 0
        with self.assertRaises(ValueError):
            self.panel.configure(gap=-1)


if __name__ == '__main__':
    unittest.main()
