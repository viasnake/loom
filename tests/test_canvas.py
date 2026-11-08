import importlib.util
from types import SimpleNamespace
import unittest

from loom.canvas import PyxelCanvas
from loom.geometry import Rect


class CanvasTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.target = SimpleNamespace(
            width=100,
            height=80,
            clip=lambda *args: self.calls.append(args),
        )
        self.canvas = PyxelCanvas(self.target)

    def test_nested_intersection_restores_after_exception(self):
        with self.canvas.clipped(Rect(10, 10, 40, 30)):
            with self.assertRaisesRegex(ValueError, "widget failed"):
                with self.canvas.clipped(Rect(30, 0, 50, 50)):
                    raise ValueError("widget failed")
            self.assertEqual(self.calls[-1], (10, 10, 40, 30))
        self.assertEqual(
            self.calls, [(10, 10, 40, 30), (30, 10, 20, 30), (10, 10, 40, 30), ()]
        )

    def test_current_surface_bounds_are_used_after_resize(self):
        self.target.width = 20
        self.target.height = 10
        with self.canvas.clipped(Rect(-10, -10, 100, 100)):
            self.assertEqual(self.calls[-1], (0, 0, 20, 10))
        self.assertEqual(self.calls[-1], ())

    def test_invalid_clip_does_not_change_backend(self):
        with self.assertRaises(ValueError):
            with self.canvas.clipped(Rect(0, 0, -1, 10)):
                pass
        self.assertEqual(self.calls, [])


@unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
class NativeCanvasTests(unittest.TestCase):
    def test_nested_and_disjoint_clips_match_pixels_and_restore(self):
        import pyxel

        # Image drawing avoids changing the process-wide screen or clip state.
        target = pyxel.Image(12, 10)
        canvas = PyxelCanvas(target)
        target.cls(0)
        with canvas.clipped(Rect(2, 2, 8, 6)):
            canvas.rect(0, 0, 12, 10, 1)
            with canvas.clipped(Rect(6, 0, 10, 10)):
                canvas.rect(0, 0, 12, 10, 2)
            with canvas.clipped(Rect(30, 30, 2, 2)):
                canvas.rect(0, 0, 12, 10, 3)
            canvas.rect(2, 2, 1, 1, 4)
        canvas.rect(0, 0, 1, 1, 5)
        for y in range(10):
            for x in range(12):
                expected = 0
                if 2 <= x < 10 and 2 <= y < 8:
                    expected = 2 if x >= 6 else 1
                if (x, y) == (2, 2):
                    expected = 4
                if (x, y) == (0, 0):
                    expected = 5
                self.assertEqual(target.pget(x, y), expected, (x, y))
