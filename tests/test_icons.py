import importlib.util
import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

from loom import (
    Button,
    Column,
    FontCatalog,
    Icon,
    PyxelCanvas,
    Theme,
    Typography,
    UIInput,
)
from loom.geometry import Rect


class RecordingCanvas:
    def __init__(self):
        self.calls = []

    def rect(self, *args):
        self.calls.append(("rect", args))

    def text(self, *args, **kwargs):
        self.calls.append(("text", args))

    def blt(self, *args):
        self.calls.append(("blt", args))


class IconTests(unittest.TestCase):
    def setUp(self):
        self.image = SimpleNamespace(width=32, height=32)

    def test_region_validation_and_resource_reference(self):
        icon = Icon(self.image)
        self.assertIs(icon.image, self.image)
        self.assertEqual(icon.region, Rect(0, 0, 32, 32))
        with self.assertRaises(FrozenInstanceError):
            icon.region = Rect(0, 0, 1, 1)
        for region in (Rect(-1, 0, 2, 2), Rect(0, 0, 0, 2), Rect(31, 0, 2, 2)):
            with self.assertRaises(ValueError):
                Icon(self.image, region)
        for region in ((0, 0, 1, 1), Rect(0, 0, 1.5, 1), Rect(True, 0, 1, 1)):
            with self.assertRaises(TypeError):
                Icon(self.image, region)
        for color in (-1, 256, True, 1.0):
            with self.assertRaises(ValueError):
                Icon(self.image, colkey=color)
        with self.assertRaises(TypeError):
            Icon(0)

    def test_icon_replacement_relayouts_once_and_preserves_explicit_height(self):
        small = Icon(self.image, Rect(0, 0, 8, 8))
        large = Icon(self.image)
        button = Button("", lambda: None, icon=small)
        panel = Column([button], width=80)
        panel.layout()
        count = panel.layout_count
        self.assertEqual(button.rect.height, 20)
        button.icon = large
        panel.layout()
        self.assertEqual(button.rect.height, 40)
        self.assertEqual(panel.layout_count, count + 1)
        button.icon = large
        panel.layout()
        self.assertEqual(panel.layout_count, count + 1)
        with self.assertRaises(TypeError):
            button.icon = self.image
        self.assertIs(button.icon, large)
        button.height = 12
        panel.layout()
        self.assertEqual(button.rect.height, 12)
        button.height = None
        button.icon = None
        panel.layout()
        self.assertEqual(button.rect.height, 20)

    def test_icon_only_and_text_alignment_with_typography(self):
        icon = Icon(self.image, Rect(3, 4, 8, 10), colkey=0)
        a = Button("", lambda: None, icon=icon)
        b = Button("Equip", lambda: None, icon=icon)
        panel = Column(
            [a, b],
            x=10,
            y=10,
            width=60,
            padding=0,
            typography=Typography(FontCatalog()),
        )
        canvas = RecordingCanvas()
        panel.draw(canvas)
        blits = [args for name, args in canvas.calls if name == "blt"]
        self.assertEqual(blits[0], (36, 15, self.image, 3, 4, 8, 10, 0))
        self.assertEqual(blits[1][:2], (14, b.rect.y + 5))
        texts = [args for name, args in canvas.calls if name == "text"]
        self.assertEqual(len(texts), 1)
        self.assertEqual(texts[0][0], 26)
        self.assertEqual(texts[0][2], "Equip")

    def test_click_keyboard_disable_and_reset_keep_existing_contract(self):
        clicked = []
        button = Button("", lambda: clicked.append("fire"), icon=Icon(self.image))
        panel = Column([button], width=64)
        panel.layout()
        x, y = button.rect.x + 8, button.rect.y + 8
        panel.update(UIInput(x, y, pointer_pressed=True))
        self.assertEqual(clicked, [])
        panel.update(UIInput(x, y, pointer_released=True))
        self.assertEqual(clicked, ["fire"])
        panel.update(UIInput(confirm=True))
        self.assertEqual(clicked, ["fire", "fire"])
        panel.update(UIInput(x, y, pointer_pressed=True))
        panel.reset_input()
        panel.update(UIInput(x, y, pointer_released=True))
        self.assertEqual(len(clicked), 2)
        button.enabled = False
        panel.update(UIInput(x, y, pointer_pressed=True))
        panel.update(UIInput(x, y, pointer_released=True, confirm=True))
        self.assertEqual(len(clicked), 2)

    def test_text_only_canvas_remains_usable_and_missing_blt_is_explicit(self):
        canvas = SimpleNamespace(rect=lambda *a: None, text=lambda *a, **k: None)
        Column([Button("OK", lambda: None)], width=80).draw(canvas)
        for typography in (None, Typography(FontCatalog())):
            with self.assertRaisesRegex(TypeError, "ImageCanvas"):
                Column(
                    [Button("", lambda: None, icon=Icon(self.image))],
                    width=80,
                    typography=typography,
                ).draw(canvas)

    @unittest.skipUnless(importlib.util.find_spec("pyxel"), "Pyxel is not installed")
    def test_native_transparency_crop_disabled_and_nested_clip(self):
        import pyxel

        source = pyxel.Image(12, 12)
        for y in range(12):
            for x in range(12):
                source.pset(x, y, 0 if (x + y) % 3 == 0 else 8 + (x + y) % 3)
        icon = Icon(source, Rect(2, 1, 9, 10), colkey=0)
        target = pyxel.Image(36, 32)
        canvas = PyxelCanvas(target)
        for width, height in ((20, 20), (13, 14), (7, 7)):
            for enabled in (True, False):
                with self.subTest(width=width, height=height, enabled=enabled):
                    target.cls(0)
                    button = Button(
                        "", lambda: None, icon=icon, height=height, enabled=enabled
                    )
                    panel = Column(
                        [button],
                        x=3,
                        y=3,
                        width=width,
                        padding=0,
                        viewport_height=height,
                        typography=Typography(FontCatalog()),
                    )
                    outer = Rect(0, 0, 17, 17)
                    with canvas.clipped(outer):
                        panel.draw(canvas)
                    r = button.rect
                    ix = r.x + max(4, (r.width - 9) // 2)
                    iy = r.y + max(4, (r.height - 10) // 2)
                    inner = Rect(
                        r.x + 4, r.y + 4, max(0, r.width - 8), max(0, r.height - 8)
                    )
                    for y in range(32):
                        for x in range(36):
                            expected = (
                                5 if r.contains(x, y) and outer.contains(x, y) else 0
                            )
                            if (
                                inner.contains(x, y)
                                and outer.contains(x, y)
                                and ix <= x < ix + 9
                                and iy <= y < iy + 10
                            ):
                                pixel = source.pget(2 + x - ix, 1 + y - iy)
                                if pixel:
                                    expected = pixel
                            self.assertEqual(target.pget(x, y), expected, (x, y))
        # The source remains game-owned and live, not copied into the Icon.
        source.pset(2, 1, 11)
        target.cls(0)
        icon.draw(canvas, 0, 0, Rect(0, 0, 36, 32))
        self.assertEqual(target.pget(0, 0), 11)
