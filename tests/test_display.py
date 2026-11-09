import json
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
    def test_config_and_viewports_copy_mutable_size_buffers(self):
        output, world = [32, 24], [8, 6]
        config = DisplayConfig(output, world)
        fitted = Viewport.fit(world, output)
        direct = Viewport(world, output, 4, 0, 0)
        output[:] = [40, 30]
        world[:] = [10, 5]
        self.assertEqual(config, DisplayConfig((32, 24), (8, 6)))
        for viewport in (fitted, direct, config.viewport()):
            with self.subTest(viewport=viewport):
                self.assertEqual(viewport.source_size, (8, 6))
                self.assertEqual(viewport.target_size, (32, 24))
                self.assertEqual((viewport.width, viewport.height), (32, 24))
                self.assertEqual(viewport.to_local(31, 23), (7.75, 5.75))
                self.assertIsNone(viewport.to_local(32, 23))

    def test_reusing_json_settings_requires_real_resize_and_preserves_active_picking(
        self,
    ):
        settings = json.loads('{"output_size":[32,24],"world_size":[8,6]}')
        allocations, resizes = [], []

        def image(width, height):
            result = SimpleNamespace(width=width, height=height)
            allocations.append(result)
            return result

        engine = SimpleNamespace(Image=image, resize=lambda *size: resizes.append(size))
        display = PyxelDisplay(engine, DisplayConfig(**settings))
        original = display.world
        settings["output_size"][:] = [40, 30]
        settings["world_size"][:] = [10, 5]
        self.assertIsNone(display.pick(35, 10))
        self.assertEqual(display.pick(31, 23), (7, 5))
        display.resize(DisplayConfig(**settings))
        self.assertEqual(resizes, [(40, 30)])
        self.assertEqual(len(allocations), 2)
        self.assertIsNot(display.world, original)
        self.assertEqual((display.world.width, display.world.height), (10, 5))
        self.assertEqual(display.pick(39, 24), (9, 4))
        self.assertIsNone(display.pick(40, 24))
        self.assertIsNone(display.pick(39, 25))

    def test_mutable_sizes_keep_existing_validation(self):
        for size in ([0, 6], [8, -1], [8, True], [8, 6.0], [8], [8, 6, 1]):
            with self.subTest(size=size), self.assertRaises(ValueError):
                DisplayConfig([32, 24], size)
            with self.subTest(size=size), self.assertRaises(ValueError):
                Viewport.fit(size, [32, 24])
        with self.assertRaises(ValueError):
            DisplayConfig([4, 3], [8, 6])

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
    def test_native_resize_from_reused_lists_keeps_pixels_and_pick_in_sync(self):
        try:
            import pyxel
        except ImportError:
            self.skipTest("optional native Pyxel test")
        initialize_native(pyxel)
        output, world = [24, 18], [8, 6]
        pyxel.resize(*output)
        display = PyxelDisplay(pyxel, DisplayConfig(output, world))
        output[:] = [42, 30]
        world[:] = [7, 5]
        queued = DisplayConfig(output, world)
        output[:] = [64, 48]
        world[:] = [16, 12]
        for expected in (((24, 18), (8, 6)), ((42, 30), (7, 5))):
            if expected[0] == (42, 30):
                display.resize(queued)
            self.assertEqual((pyxel.width, pyxel.height), expected[0])
            self.assertEqual((display.world.width, display.world.height), expected[1])
            for y in range(expected[1][1]):
                for x in range(expected[1][0]):
                    display.world.pset(x, y, 1 + x + y * expected[1][0])
            display.composite()
            for y in range(expected[0][1]):
                for x in range(expected[0][0]):
                    point = display.pick(x, y)
                    self.assertIsNotNone(point)
                    self.assertEqual(pyxel.pget(x, y), display.world.pget(*point))
            self.assertIsNone(display.pick(expected[0][0], 0))

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
