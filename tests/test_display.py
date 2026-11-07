import unittest
from types import SimpleNamespace
from loom.display import DisplayConfig, Viewport, PyxelDisplay


class DisplayTests(unittest.TestCase):
    def test_integer_letterbox_and_edges(self):
        v = Viewport.fit((320, 180), (1000, 600))
        self.assertEqual((v.scale, v.x, v.y), (3, 20, 30))
        self.assertEqual(v.to_local(20, 30), (0, 0))
        self.assertIsNone(v.to_local(19, 30))
        self.assertIsNone(v.to_local(980, 30))
        self.assertIsNone(v.to_local(float('nan'), 30))
        self.assertEqual(v.to_local(*v.to_output(15, 22)), (15, 22))

    def test_fit_downscale_and_validation(self):
        self.assertEqual(Viewport.fit((640, 360), (320, 180), integer=False).scale, .5)
        for kwargs in [dict(world_size=(0, 10)), dict(output_size=(10, 10)), dict(scale='stretch')]:
            with self.assertRaises(ValueError):
                DisplayConfig(**kwargs)

    def test_composite_centered_scale_and_reuse(self):
        calls = []
        engine = SimpleNamespace(Image=lambda w,h: object(),
                                 resize=lambda *args: calls.append(('resize', args)),
                                 cls=lambda color: calls.append(('cls', color)),
                                 blt=lambda *args, **kwargs: calls.append(('blt', args, kwargs)))
        display = PyxelDisplay(engine)
        world = display.world
        display.composite()
        _, args, kwargs = calls[-1]
        self.assertEqual(args[:2], (320, 180))
        self.assertEqual(kwargs, {'scale': 3})
        display.resize(DisplayConfig(output_size=(1280, 720)))
        self.assertIs(display.world, world)
        self.assertEqual(calls[-1], ('resize', (1280,720)))
        display.resize(DisplayConfig(output_size=(1280,720), world_size=(640,360)))
        self.assertIsNot(display.world, world)
