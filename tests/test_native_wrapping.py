"""Wrapped layout and real Pyxel pixels must agree on line positions."""

import importlib.util
import unittest

from loom import Column, Label, PyxelCanvas


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeWrappingTests(unittest.TestCase):
    def test_wrap_reflow_and_scroll_match_explicit_line_rendering(self):
        import pyxel

        target = pyxel.Image(64, 64)
        expected = pyxel.Image(64, 64)
        label = Label("one two three", wrap=True)
        panel = Column([label], x=3, y=4, width=16, padding=2, viewport_height=16)
        # Three character cells fit initially. Widening fits both first words.
        for width, lines, scroll in (
            (16, ("one", "two", "thr", "ee"), 0),
            (16, ("one", "two", "thr", "ee"), 6),
            (32, ("one two", "three"), 0),
        ):
            with self.subTest(width=width, scroll=scroll):
                panel.configure(width=width)
                panel.scroll_offset = scroll
                target.cls(0)
                panel.draw(PyxelCanvas(target))
                expected.cls(0)
                expected.rect(3, 4, width, 16, panel.theme.panel)
                expected.clip(5, 6, width - 4, 12)
                for index, line in enumerate(lines):
                    expected.text(5, 6 + index * 6 - scroll, line, panel.theme.text)
                expected.clip()
                for y in range(64):
                    for x in range(64):
                        self.assertEqual(target.pget(x, y), expected.pget(x, y), (x, y))
