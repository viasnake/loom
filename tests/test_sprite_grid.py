import importlib.util
import unittest

from loom import SpriteClip, SpritePlayer


class SpriteGridTests(unittest.TestCase):
    def test_row_major_offsets_gaps_and_partial_last_row(self):
        clip = SpriteClip.from_grid(
            (8, 6), columns=3, count=5, origin=(2, 4), spacing=(1, 3), fps=4
        )
        self.assertEqual(
            clip.frames,
            ((2, 4, 8, 6), (11, 4, 8, 6), (20, 4, 8, 6), (2, 13, 8, 6), (11, 13, 8, 6)),
        )
        self.assertEqual(clip.duration, 1.25)
        player = SpritePlayer(clip, loop=False)
        for frame in clip.frames:
            self.assertEqual(player.frame, frame)
            self.assertFalse(player.finished)
            player.update(0.25)
        self.assertTrue(player.finished)
        self.assertEqual(player.frame, clip.frames[-1])

    def test_default_gaps_single_column_and_short_first_row(self):
        self.assertEqual(
            SpriteClip.from_grid((2, 3), columns=1, count=3).frames,
            ((0, 0, 2, 3), (0, 3, 2, 3), (0, 6, 2, 3)),
        )
        self.assertEqual(
            SpriteClip.from_grid((2, 3), columns=9, count=2),
            SpriteClip(((0, 0, 2, 3), (2, 0, 2, 3))),
        )

    def test_mutable_arguments_are_not_retained(self):
        size, origin, spacing = [2, 3], [4, 5], [1, 2]
        clip = SpriteClip.from_grid(
            size, columns=2, count=3, origin=origin, spacing=spacing
        )
        size[0] = origin[0] = spacing[0] = 99
        self.assertEqual(clip.frames, ((4, 5, 2, 3), (7, 5, 2, 3), (4, 10, 2, 3)))

    def test_invalid_dimensions_counts_and_coordinates(self):
        defaults = dict(frame_size=(2, 3), columns=2, count=3)
        for name in ("columns", "count"):
            for value in (0, -1, True, 1.5, "2", None):
                with (
                    self.subTest(name=name, value=value),
                    self.assertRaises(ValueError),
                ):
                    SpriteClip.from_grid(**(defaults | {name: value}))
        for name in ("frame_size", "origin", "spacing"):
            invalid = [
                (),
                (1,),
                (1, 2, 3),
                (-1, 2),
                (1, -1),
                (True, 2),
                (1, False),
                (1.0, 2),
                "12",
                None,
                2,
            ]
            if name == "frame_size":
                invalid += [(0, 2), (1, 0)]
            for value in invalid:
                with (
                    self.subTest(name=name, value=value),
                    self.assertRaises(ValueError),
                ):
                    SpriteClip.from_grid(**(defaults | {name: value}))
        for fps in (0, -1, True, float("inf"), float("nan"), 5e-324):
            with self.subTest(fps=fps), self.assertRaises(ValueError):
                SpriteClip.from_grid(**defaults, fps=fps)

    @unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
    def test_native_blits_exclude_gaps_and_follow_row_order(self):
        import pyxel

        # The expected coordinates are independent of the grid implementation.
        sheet = pyxel.Image(19, 15)
        sheet.cls(8)
        positions = ((2, 3), (8, 3), (14, 3), (2, 10), (8, 10))
        for color, (x, y) in enumerate(positions, 1):
            sheet.rect(x, y, 4, 3, color)
            sheet.pset(x + 3, y + 2, 7)
        clip = SpriteClip.from_grid(
            (4, 3), columns=3, count=5, origin=(2, 3), spacing=(2, 4), fps=4
        )
        target = pyxel.Image(6, 5)
        player = SpritePlayer(clip)
        for index in range(6):
            target.cls(0)
            target.blt(1, 1, sheet, *player.frame)
            color = index % 5 + 1
            for y in range(5):
                for x in range(6):
                    expected = (
                        7
                        if (x, y) == (4, 3)
                        else color if 1 <= x < 5 and 1 <= y < 4 else 0
                    )
                    self.assertEqual(target.pget(x, y), expected, (index, x, y))
            player.update(0.25)
