"""Frequently changing HUD text must not rebuild unrelated widget geometry."""

import importlib.util
import unittest

from loom import Button, Column, FontCatalog, Label, PyxelCanvas, Typography, UIInput


class Canvas:
    def __init__(self):
        self.texts = []

    def rect(self, *args):
        pass

    def text(self, x, y, text, color, **kwargs):
        self.texts.append((x, y, text))


class DynamicLabelTests(unittest.TestCase):
    def test_fixed_hud_updates_draw_current_text_without_relayout(self):
        label = Label("OXYGEN 100%", height=12)
        button = Button("Pause", lambda: None)
        panel = Column([label, button], width=120)
        panel.update(UIInput(next_focus=True))
        initial = (panel.layout_count, label.rect, button.rect)
        for tick in range(1000):
            label.text = f"OXYGEN {tick % 101}%"
            panel.update(UIInput())
            canvas = Canvas()
            panel.draw(canvas)
            self.assertEqual(canvas.texts[0][2], label.text)
        self.assertEqual((panel.layout_count, label.rect, button.rect), initial)
        self.assertIs(panel.focused, button)
        with self.assertRaises(TypeError):
            label.text = 5
        self.assertEqual(label.text, "OXYGEN 90%")

    def test_geometry_changes_and_font_revision_still_relayout(self):
        fonts = FontCatalog()
        label = Label("One", height=12)
        button = Button("Pause", lambda: None)
        panel = Column([label, button], width=100, gap=2, typography=Typography(fonts))
        panel.layout()
        label.text = "One\nTwo\nThree"
        panel.layout()
        self.assertEqual(panel.layout_count, 1)
        self.assertEqual(label.rect.height, 12)
        panel.configure(width=140, padding=6)
        panel.layout()
        self.assertEqual(panel.layout_count, 2)
        self.assertEqual((label.rect.x, label.rect.width), (6, 128))
        label.height = None
        panel.layout()
        self.assertEqual(label.rect.height, 18)
        self.assertEqual(button.rect.y, label.rect.y + 18 + 2)
        label.height = 24
        panel.layout()
        fonts.register("default", line_height=10)
        panel.layout()
        self.assertEqual(panel.layout_count, 5)
        self.assertEqual(label.rect.height, 24)
        label.visible = False
        panel.layout()
        self.assertEqual(button.rect.y, 6)
        label.visible = True
        panel.layout()
        self.assertEqual(button.rect.y, 6 + 24 + 2)

    def test_wrapping_refreshes_lines_and_switching_back_draws_new_text(self):
        label = Label("abcd", height=30)
        panel = Column([label], width=24)
        panel.layout()
        label.wrap = True
        label.text = "abcdefghij"
        panel.layout()
        self.assertEqual(label._lines, ("abcd", "efgh", "ij"))
        label.text = "xyz"
        panel.layout()
        self.assertEqual(label._lines, ("xyz",))
        label.wrap = False
        label.text = "raw\ntext"
        canvas = Canvas()
        panel.draw(canvas)
        self.assertEqual(canvas.texts[0][2], "raw\ntext")
        count = panel.layout_count
        label.text = "new"
        panel.draw(Canvas())
        self.assertEqual(panel.layout_count, count)

    def test_auto_height_buttons_and_custom_labels_keep_text_invalidation(self):
        class CustomLabel(Label):
            def measure_height(self, width, typography):
                return len(self.text) * 2

        for widget in (
            Label("a"),
            Button("a", lambda: None, height=30),
            CustomLabel("a", height=12),
        ):
            with self.subTest(widget=type(widget).__name__):
                panel = Column([widget], width=100)
                panel.layout()
                widget.text = "a\nb\nc"
                panel.layout()
                self.assertEqual(panel.layout_count, 2)
                if isinstance(widget, Button):
                    self.assertEqual(widget._text_height, 18)
                elif type(widget) is Label:
                    self.assertEqual(widget.rect.height, 18)
                else:
                    self.assertEqual(widget.rect.height, 10)

    @unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
    def test_native_repeated_hud_matches_fresh_layout_pixels(self):
        import pyxel

        label = Label("0", height=12)
        panel = Column([label, Button("Pause", lambda: None)], width=80)
        retained = pyxel.Image(80, 44)
        fresh = pyxel.Image(80, 44)
        for text in ("100%", "8%", "", "Two\nlines", "9%"):
            label.text = text
            retained.cls(0)
            panel.draw(PyxelCanvas(retained))
            reference = Column(
                [Label(text, height=12), Button("Pause", lambda: None)], width=80
            )
            fresh.cls(0)
            reference.draw(PyxelCanvas(fresh))
            self.assertEqual(
                [retained.pget(x, y) for y in range(44) for x in range(80)],
                [fresh.pget(x, y) for y in range(44) for x in range(80)],
            )
        self.assertEqual(panel.layout_count, 1)
