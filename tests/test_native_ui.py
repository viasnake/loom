import importlib.util
import unittest

from loom import Column, PyxelCanvas
from loom.geometry import Rect
from loom.ui import Widget


class OversizedPaint(Widget):
    def __init__(self):
        super().__init__(height=20)

    def draw(self, canvas, theme, **state):
        # A deliberately overpainting child must not escape its viewport.
        canvas.rect(-100, -100, 300, 300, 3)


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeViewportTests(unittest.TestCase):
    def test_children_cannot_paint_outside_viewport_or_outer_clip(self):
        import pyxel

        target = pyxel.Image(60, 50)
        canvas = PyxelCanvas(target)
        panel = Column(
            [OversizedPaint(), OversizedPaint()],
            x=4,
            y=4,
            width=40,
            viewport_height=30,
            padding=2,
        )
        for outer in (Rect(0, 0, 60, 50), Rect(0, 0, 20, 20)):
            with self.subTest(outer=outer):
                target.cls(0)
                with canvas.clipped(outer):
                    panel.draw(canvas)
                    # The panel restores the caller's clip, not full-screen.
                    canvas.rect(0, 0, 1, 1, 5)
                for y in range(50):
                    for x in range(60):
                        expected = 0
                        if outer.contains(x, y):
                            if Rect(4, 4, 40, 30).contains(x, y):
                                expected = 1
                            if Rect(6, 6, 36, 26).contains(x, y):
                                expected = 3
                            if (x, y) == (0, 0):
                                expected = 5
                        self.assertEqual(target.pget(x, y), expected, (x, y))
