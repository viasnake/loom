import unittest
from types import SimpleNamespace
from loom.palette import Palette


class PaletteTests(unittest.TestCase):
    def test_stable_aliases(self):
        p = Palette({'background': 0, 'text': 0xFFFFFF, 'paper': 0xFFFFFF})
        self.assertEqual(p.colors, (0, 0xFFFFFF))
        self.assertEqual(p['paper'], 1)
        with self.assertRaises(KeyError): p['missing']
        with self.assertRaises(TypeError): p.names['extra'] = 2
        applied = []
        p.apply(SimpleNamespace(colors=applied))
        self.assertEqual(applied, [0, 0xFFFFFF])

    def test_limits(self):
        self.assertEqual(len(Palette({str(i): i for i in range(256)}).colors), 256)
        for colors in [{}, {'': 0}, {'bad': -1}, {'bad': True}, {'bad': 0x1000000},
                       {str(i): i for i in range(257)}]:
            with self.assertRaises(ValueError): Palette(colors)
