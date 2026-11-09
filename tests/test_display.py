import unittest
from types import SimpleNamespace
from loom.display import DisplayConfig, Viewport, PyxelDisplay


_native_initialized = False


def initialize_native(pyxel):
    global _native_initialized
    if not _native_initialized:
        pyxel.init(48, 48, headless=True, capture_sec=0)
        _native_initialized = True


class DisplayTests(unittest.TestCase):
    def test_integer_letterbox_and_edges(self):
        v = Viewport.fit((320, 180), (1000, 600))
        self.assertEqual((v.scale, v.x, v.y), (3, 20, 30))
        self.assertEqual(v.to_local(20, 30), (0, 0))
        self.assertIsNone(v.to_local(19, 30))
        self.assertIsNone(v.to_local(980, 30))
        self.assertIsNone(v.to_local(float("nan"), 30))
        self.assertEqual(v.to_local(*v.to_output(15, 22)), (15, 22))

    def test_fit_downscale_and_validation(self):
        self.assertEqual(Viewport.fit((640, 360), (320, 180), integer=False).scale, 0.5)
        for kwargs in [
            dict(world_size=(0, 10)),
            dict(output_size=(10, 10)),
            dict(scale="stretch"),
        ]:
            with self.assertRaises(ValueError):
                DisplayConfig(**kwargs)

    def test_composite_centered_scale_and_reuse(self):
        calls = []
        engine = SimpleNamespace(
            Image=lambda w, h: object(),
            resize=lambda *args: calls.append(("resize", args)),
            cls=lambda color: calls.append(("cls", color)),
            blt=lambda *args, **kwargs: calls.append(("blt", args, kwargs)),
        )
        display = PyxelDisplay(engine)
        world = display.world
        display.composite()
        _, args, kwargs = calls[-1]
        self.assertEqual(args[:2], (320, 180))
        self.assertEqual(kwargs, {"scale": 3})
        display.resize(DisplayConfig(output_size=(1280, 720)))
        self.assertIs(display.world, world)
        self.assertEqual(calls[-1], ("resize", (1280, 720)))
        display.resize(DisplayConfig(output_size=(1280, 720), world_size=(640, 360)))
        self.assertIsNot(display.world, world)

    def test_odd_letterbox_pixels_have_integer_origins(self):
        viewport = Viewport.fit((4, 2), (21, 21))
        self.assertEqual((viewport.x, viewport.y), (0, 5))
        self.assertEqual(viewport.to_local(0, 5), (0, 0))
        self.assertIsNone(viewport.to_local(20, 5))

    def test_odd_image_uses_even_copy_rectangle(self):
        calls = []
        engine = SimpleNamespace(
            Image=lambda w, h: object(),
            cls=lambda color: None,
            blt=lambda *args, **kwargs: calls.append((args, kwargs)),
        )
        display = PyxelDisplay(engine, DisplayConfig((6, 6), (3, 3)))
        display.composite()
        args, kwargs = calls[-1]
        self.assertEqual(args[:2], (2, 2))
        self.assertEqual(args[5:7], (4, 4))
        self.assertEqual(kwargs["scale"], 2)


class NativeDisplayTests(unittest.TestCase):
    def test_integer_composite_matches_viewport_pixels(self):
        try:
            import pyxel
        except ImportError:
            self.skipTest("optional native Pyxel test")
        initialize_native(pyxel)
        for size in (1, 2, 3, 4, 5):
            for scale in (1, 2, 3, 4):
                with self.subTest(size=size, scale=scale):
                    output = size * scale + 1
                    display = PyxelDisplay(
                        pyxel, DisplayConfig((output, output), (size, size))
                    )
                    pyxel.resize(output, output)
                    display.world.cls(2)
                    display.composite()
                    viewport = display.viewport
                    for y in range(output):
                        for x in range(output):
                            expected = 2 if viewport.to_local(x, y) is not None else 0
                            self.assertEqual(pyxel.pget(x, y), expected)


class RasterPickingTests(unittest.TestCase):
    def engine(self):
        return SimpleNamespace(
            Image=lambda w, h: object(),
            resize=lambda *args: None,
            cls=lambda *args: None,
            blt=lambda *args, **kwargs: None,
        )

    def test_fractional_pixel_mapping_and_outside_points(self):
        display = PyxelDisplay(self.engine(), DisplayConfig((7, 7), (5, 3), "fit"))
        self.assertIsNone(display.viewport.to_local(1, 1))
        self.assertEqual(display.pick(1, 1), (1, 0))
        self.assertEqual(
            [display.pick(x, 1)[0] for x in range(7)], [0, 1, 1, 2, 3, 4, 4]
        )
        self.assertEqual(display.pick(1.9, 1.9), (1, 0))
        for point in (
            (0, 0),
            (-0.1, 1),
            (7, 1),
            (1, 7),
            (1, float("nan")),
            (float("inf"), 1),
        ):
            self.assertIsNone(display.pick(*point))

    def test_resize_failure_keeps_old_pick_tables_and_composite_does_not_rebuild(self):
        from unittest.mock import patch

        engine = self.engine()
        display = PyxelDisplay(engine, DisplayConfig((7, 7), (5, 3), "fit"))
        original = display.config, display.world, display._pick_x, display._pick_y

        def fail_resize(*args):
            raise RuntimeError("resize")

        engine.resize = fail_resize
        with self.assertRaises(RuntimeError):
            display.resize(DisplayConfig((9, 9), (5, 3), "fit"))
        self.assertEqual(
            (display.config, display.world, display._pick_x, display._pick_y), original
        )
        with patch(
            "loom.display._raster_indices", side_effect=AssertionError("rebuilt")
        ):
            display.composite()
            self.assertEqual(display.pick(1, 1), (1, 0))
        self.assertEqual(len(display._pick_x) + len(display._pick_y), 14)
        self.assertEqual(display._pick_x.typecode, "i")

    def test_native_seeded_raster_color_matches_pick_in_all_modes(self):
        import random

        try:
            import pyxel
        except ImportError:
            self.skipTest("optional native Pyxel test")
        initialize_native(pyxel)
        rng = random.Random(61)
        cases = [(5, 3, 7, 7), (7, 4, 3, 3), (1, 1, 7, 9), (1, 5, 3, 2), (5, 1, 2, 3)]
        cases += [
            (
                rng.randrange(1, 13),
                rng.randrange(1, 13),
                rng.randrange(1, 25),
                rng.randrange(1, 25),
            )
            for _ in range(200)
        ]
        for w, h, tw, th in cases:
            for mode in ("fit", "integer"):
                if mode == "integer" and (w > tw or h > th):
                    continue
                with self.subTest(size=(w, h, tw, th), mode=mode):
                    pyxel.resize(tw, th)
                    display = PyxelDisplay(pyxel, DisplayConfig((tw, th), (w, h), mode))
                    for y in range(h):
                        for x in range(w):
                            display.world.pset(x, y, 1 + x + y * w)
                    display.composite()
                    for y in range(th):
                        for x in range(tw):
                            point = display.pick(x, y)
                            expected = (
                                0 if point is None else 1 + point[0] + point[1] * w
                            )
                            self.assertEqual(pyxel.pget(x, y), expected, (x, y, point))
        # Longer scanlines exercise accumulated float32 rounding, not just centers.
        for w, h, tw, th in (
            (321, 181, 970, 620),
            (320, 180, 777, 513),
            (639, 359, 321, 181),
        ):
            pyxel.resize(tw, th)
            display = PyxelDisplay(pyxel, DisplayConfig((tw, th), (w, h), "fit"))
            for x in range(w):
                display.world.rect(x, 0, 1, h, 1 + x % 255)
            display.composite()
            for y in (0, th // 4, th // 2, th - 1):
                for x in range(tw):
                    point = display.pick(x, y)
                    self.assertEqual(
                        pyxel.pget(x, y), 0 if point is None else 1 + point[0] % 255
                    )
            for y in range(h):
                display.world.rect(0, y, w, 1, 1 + y % 255)
            display.composite()
            for y in range(th):
                for x in (0, tw // 2, tw - 1):
                    point = display.pick(x, y)
                    self.assertEqual(
                        pyxel.pget(x, y), 0 if point is None else 1 + point[1] % 255
                    )
