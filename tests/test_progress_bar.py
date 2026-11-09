import importlib.util
import math
import unittest

from loom import Button, Column, ProgressBar, PyxelCanvas, Theme, UIInput
from loom.geometry import Rect


class ProgressBarTests(unittest.TestCase):
    def test_clamps_finite_values_and_rejects_invalid_without_mutation(self):
        bar = ProgressBar()
        for value, expected in ((-2, 0), (0, 0), (0.25, 0.25), (1, 1), (3, 1)):
            bar.value = value
            self.assertEqual(bar.value, expected)
        for value in (True, "0.5", None, math.inf, -math.inf, math.nan, 10**1000):
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                bar.value = value
            self.assertEqual(bar.value, 1)
        for color in (-1, 256, True, 1.0):
            with self.assertRaises(ValueError):
                ProgressBar(color=color)

    def test_value_updates_preserve_layout_and_keyboard_skips_bar(self):
        clicks = []
        first = Button("First", lambda: clicks.append("first"))
        bar = ProgressBar()
        last = Button("Last", lambda: clicks.append("last"))
        panel = Column([first, bar, last], width=100)
        panel.layout()
        count, bounds = panel.layout_count, bar.rect
        for value in range(101):
            bar.value = value / 100
            panel.layout()
        self.assertEqual(panel.layout_count, count)
        self.assertEqual(bar.rect, bounds)
        panel.update(UIInput(next_focus=True))
        self.assertIs(panel.focused, first)
        panel.update(UIInput(next_focus=True, confirm=True))
        self.assertIs(panel.focused, last)
        self.assertEqual(clicks, ["last"])

    def test_pointer_does_not_edit_bar_or_steal_keyboard_focus(self):
        bar = ProgressBar(0.5)
        button = Button("Action", lambda: None)
        panel = Column([button, bar], width=100)
        panel.update(UIInput(next_focus=True))
        x, y = bar.rect.x + 1, bar.rect.y + 1
        self.assertTrue(
            panel.update(UIInput(x, y, pointer_pressed=True)).pointer_consumed
        )
        self.assertTrue(
            panel.update(UIInput(x, y, pointer_released=True)).pointer_consumed
        )
        self.assertEqual(bar.value, 0.5)
        self.assertIs(panel.focused, button)

    @unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
    def test_native_pixels_endpoints_theme_disabled_and_narrow_width(self):
        import pyxel

        image = pyxel.Image(25, 15)
        theme = Theme(button=2, focus=10, disabled=6)
        for width in (1, 7, 19):
            for value in (0, 0.1, 0.5, 1):
                for enabled in (True, False):
                    for color in (None, 11):
                        with self.subTest(
                            width=width, value=value, enabled=enabled, color=color
                        ):
                            image.cls(0)
                            bar = ProgressBar(value, color=color, enabled=enabled)
                            bar.rect = Rect(2, 3, width, 5)
                            bar.draw(PyxelCanvas(image), theme)
                            fill = (
                                (theme.focus if color is None else color)
                                if enabled
                                else theme.disabled
                            )
                            for y in range(15):
                                for x in range(25):
                                    expected = 0
                                    if bar.rect.contains(x, y):
                                        expected = (
                                            fill
                                            if x - 2 < math.floor(width * value)
                                            else theme.button
                                        )
                                    self.assertEqual(image.pget(x, y), expected)

    @unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
    def test_native_progress_respects_scroll_viewport_and_outer_clip(self):
        import pyxel

        image = pyxel.Image(40, 30)
        canvas = PyxelCanvas(image)
        bars = [ProgressBar(1, color=11, height=10) for _ in range(3)]
        panel = Column(bars, x=4, y=4, width=30, viewport_height=20, padding=2, gap=2)
        panel.scroll_offset = 7
        outer = Rect(0, 0, 20, 30)
        with canvas.clipped(outer):
            panel.draw(canvas)
        content = Rect(6, 6, 26, 16)
        for y in range(30):
            for x in range(40):
                expected = 0
                if outer.contains(x, y) and panel.rect.contains(x, y):
                    expected = 1
                    if content.contains(x, y) and any(
                        b.rect.contains(x, y) for b in bars
                    ):
                        expected = 11
                self.assertEqual(image.pget(x, y), expected, (x, y))
