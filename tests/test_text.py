import unittest
from types import SimpleNamespace
from loom.text import FontCatalog


class FontTests(unittest.TestCase):
    def test_multiline_and_font_replacement(self):
        catalog = FontCatalog()
        self.assertEqual(catalog.measure("abc\nx"), (12, 12))
        catalog.register(
            "body", SimpleNamespace(text_width=lambda s: len(s) * 10), line_height=14
        )
        self.assertEqual(catalog.measure("日本語", "body"), (30, 14))
        catalog.register(
            "body", SimpleNamespace(text_width=lambda s: len(s) * 8), line_height=12
        )
        self.assertEqual(catalog.measure("日本語", "body"), (24, 12))

    def test_wrap_and_cache_bounds(self):
        catalog = FontCatalog(max_entries=3)
        self.assertEqual(
            catalog.wrap("one two\n\nabcde", 12), ("one", "two", "", "abc", "de")
        )
        self.assertEqual(catalog.wrap("字", 1), ("字",))
        for i in range(20):
            catalog.measure(str(i))
        self.assertLessEqual(catalog.cache_size, 3)
        no_cache = FontCatalog(0)
        no_cache.measure("x")
        self.assertEqual(no_cache.cache_size, 0)
        with self.assertRaises(ValueError):
            catalog.wrap("x", 0)
        with self.assertRaises(KeyError):
            catalog.measure("", "missing")

    def test_draw_uses_catalog_line_height(self):
        catalog = FontCatalog()
        calls = []
        catalog.draw(
            SimpleNamespace(text=lambda *a, **kw: calls.append((a, kw))),
            1,
            2,
            "a\nb",
            7,
        )
        self.assertEqual(calls[1], ((1, 8, "b", 7), {"font": None}))

    def test_wrap_whitespace_contract_and_draw_agree(self):
        catalog = FontCatalog()
        self.assertEqual(catalog.wrap(" a  b\t c \n\n", 20), ("a b c", "", ""))
        self.assertEqual(catalog.measure(""), (0, 6))
        self.assertEqual(catalog.measure("a\n"), (4, 12))
