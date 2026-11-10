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


class WrappingWorkTests(unittest.TestCase):
    @staticmethod
    def reference(text, width, measure):
        """Original greedy algorithm, independent of optimized implementation."""
        result = []
        for paragraph in text.split("\n"):
            line = ""
            for word in paragraph.split():
                candidate = f"{line} {word}" if line else word
                if measure(candidate) <= width:
                    line = candidate
                    continue
                if line:
                    result.append(line)
                    line = ""
                for char in word:
                    if line and measure(line + char) > width:
                        result.append(line)
                        line = ""
                    line += char
            result.append(line)
        return tuple(result)

    def test_seeded_output_matches_original_for_fixed_and_nonmonotonic_fonts(self):
        import random

        rng = random.Random(438)
        custom_width = lambda s: len(s) * 5 if len(s) % 3 else 2
        catalog = FontCatalog()
        catalog.register("custom", SimpleNamespace(text_width=custom_width))
        cases = ["", "字", " a  b\t c \n\n", "a\n", "abc defghijk"]
        cases += [
            "".join(rng.choice("abc日本語 \t\n") for _ in range(rng.randrange(120)))
            for _ in range(200)
        ]
        for text in cases:
            for width in (1, 3, 4, 7, 8, 12, 27, 480):
                self.assertEqual(
                    catalog.wrap(text, width),
                    self.reference(text, width, lambda s: len(s) * 4),
                )
                self.assertEqual(
                    catalog.wrap(text, width, "custom"),
                    self.reference(text, width, custom_width),
                )

    def test_prefixes_do_not_evict_shared_measurement(self):
        calls = []
        catalog = FontCatalog(3)
        catalog.register(
            "custom", SimpleNamespace(text_width=lambda s: calls.append(s) or len(s))
        )
        catalog.measure("retained", "custom")
        catalog.wrap("x" * 100, 50, "custom")
        self.assertEqual(catalog.cache_size, 2)
        before = len(calls)
        catalog.measure("retained", "custom")
        catalog.wrap("x" * 100, 50, "custom")
        self.assertEqual(len(calls), before)

    def test_local_cache_reuses_repeated_custom_prefixes(self):
        calls = []
        catalog = FontCatalog()
        catalog.register(
            "custom", SimpleNamespace(text_width=lambda s: calls.append(s) or len(s))
        )
        catalog.wrap("x" * 1000, 10, "custom")
        self.assertEqual(len(calls), 11)  # Whole token plus prefixes of 2..11.
        self.assertEqual(catalog.cache_size, 1)
        catalog.clear_cache()
        catalog.wrap("x" * 1000, 10, "custom")
        self.assertEqual(len(calls), 22)  # Temporary measurements were discarded.

    def test_builtin_long_token_never_uses_measurement_cache(self):
        catalog = FontCatalog()
        catalog.measure = lambda *args: self.fail("builtin wrap must use arithmetic")
        text = "a" * 100000
        self.assertEqual(catalog.wrap(text, 40000), ("a" * 10000,) * 10)
        self.assertEqual(catalog.cache_size, 1)
        self.assertEqual(catalog.wrap("a " * 50000, 400000), ("a " * 49999 + "a",))


class JapanesePunctuationTests(unittest.TestCase):
    def test_opt_in_avoids_punctuation_and_opening_brackets(self):
        catalog = FontCatalog()
        self.assertEqual(catalog.wrap("あいう、えお", 12), ("あいう", "、えお"))
        self.assertEqual(
            catalog.wrap("あいう、えお", 12, japanese_punctuation=True),
            ("あい", "う、え", "お"),
        )
        self.assertEqual(
            catalog.wrap("あい「うえ」", 12, japanese_punctuation=True),
            ("あい", "「う", "え」"),
        )
        for opening, closing in zip(
            "([{（［｛〈《「『【〔〖〘〚",
            ")] }）］｝〉》」』】〕〗〙〛".replace(" ", ""),
        ):
            self.assertEqual(
                catalog.wrap(
                    "あい" + opening + "うえ" + closing, 12, japanese_punctuation=True
                ),
                ("あい", opening + "う", "え" + closing),
            )

    def test_mixed_words_whitespace_and_explicit_lines(self):
        catalog = FontCatalog()
        self.assertEqual(
            catalog.wrap(
                " HP  10。回復します。\n\n「\n、\n", 24, japanese_punctuation=True
            ),
            ("HP", "10。回復し", "ます。", "", "「", "、", ""),
        )
        self.assertEqual(
            catalog.wrap("one two three", 24, japanese_punctuation=True),
            ("one", "two", "three"),
        )
        self.assertEqual(catalog.wrap("\t \n", 1, japanese_punctuation=True), ("", ""))

    def test_impossible_boundaries_prioritize_width_and_make_progress(self):
        catalog = FontCatalog()
        for width in (1, 4):
            self.assertEqual(
                catalog.wrap("「あ」、。", width, japanese_punctuation=True),
                ("「", "あ", "」", "、", "。"),
            )
        self.assertEqual(
            catalog.wrap("「「「あ", 8, japanese_punctuation=True), ("「「", "「あ")
        )

    def test_seeded_width_and_character_preservation_including_custom_fonts(self):
        import random

        rng = random.Random(57)
        catalog = FontCatalog(3)
        measures = (lambda s: len(s) * 4, lambda s: len(s) * 3 if len(s) % 3 else 1)
        catalog.register("custom", SimpleNamespace(text_width=measures[1]))
        for _ in range(100):
            text = "".join(rng.choice("abc日本、。！？「」() \t") for _ in range(80))
            for font, measure in zip(("default", "custom"), measures):
                for width in (1, 4, 8, 17, 80):
                    lines = catalog.wrap(text, width, font, japanese_punctuation=True)
                    self.assertEqual(
                        "".join(lines).replace(" ", ""), "".join(text.split())
                    )
                    self.assertTrue(all(lines))
                    self.assertTrue(all(line == line.strip() for line in lines))
                    self.assertTrue(
                        all(measure(line) <= width or len(line) == 1 for line in lines)
                    )
            self.assertLessEqual(catalog.cache_size, 3)

    def test_policy_is_cached_separately_and_font_replacement_invalidates(self):
        calls = []
        catalog = FontCatalog()
        catalog.register(
            "body", SimpleNamespace(text_width=lambda s: calls.append(s) or len(s) * 4)
        )
        old = catalog.wrap("あいう、えお", 12, "body")
        new = catalog.wrap("あいう、えお", 12, "body", japanese_punctuation=True)
        self.assertNotEqual(old, new)
        before = len(calls)
        self.assertEqual(
            catalog.wrap("あいう、えお", 12, "body", japanese_punctuation=True), new
        )
        self.assertEqual(len(calls), before)
        catalog.register("body", SimpleNamespace(text_width=lambda s: len(s)))
        self.assertEqual(
            catalog.wrap("あいう、えお", 12, "body", japanese_punctuation=True),
            ("あいう、えお",),
        )
        with self.assertRaises(TypeError):
            catalog.wrap("a", 12, japanese_punctuation=1)
