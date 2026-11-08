from contextlib import contextmanager
import unittest

from loom.text import FontCatalog
from loom.ui import Button, Column, Label, Theme, Typography, UIInput, Widget


class Canvas:
    def __init__(self):
        self.texts = []
        self.clips = []

    def rect(self, *args):
        pass

    def text(self, *args, **kwargs):
        self.texts.append((args, kwargs))

    @contextmanager
    def clipped(self, rect):
        self.clips.append(rect)
        yield


class WrappedLabelTests(unittest.TestCase):
    def draw(self, panel):
        canvas = Canvas()
        panel.draw(canvas)
        return canvas

    def test_default_label_preserves_text_without_wrapping(self):
        label = Label("one two three")
        panel = Column([label], width=24)
        canvas = self.draw(panel)
        self.assertEqual(label.rect.height, 12)
        self.assertEqual(canvas.texts[0][0], (4, 4, "one two three", 7))

    def test_opt_in_wrap_uses_content_width_and_plain_canvas(self):
        label = Label("one two three", wrap=True, color=3)
        panel = Column([label], width=28, padding=4)
        canvas = self.draw(panel)
        self.assertEqual(label.rect.height, 18)
        self.assertEqual(
            [entry[0] for entry in canvas.texts],
            [(4, 4, "one", 3), (4, 10, "two", 3), (4, 16, "three", 3)],
        )
        self.assertTrue(all(not kwargs for _, kwargs in canvas.texts))

    def test_text_width_padding_and_wrap_changes_relayout(self):
        label = Label("abcdefgh", wrap=True)
        panel = Column([label], width=24)
        panel.layout()
        self.assertEqual(label.rect.height, 12)
        panel.configure(width=16)
        panel.layout()
        self.assertEqual(label.rect.height, 24)
        panel.configure(padding=6)
        panel.layout()
        self.assertEqual(label.rect.height, 48)
        label.text = "abcd"
        panel.layout()
        self.assertEqual(label.rect.height, 24)
        label.wrap = False
        panel.layout()
        self.assertEqual(label.rect.height, 12)
        canvas = self.draw(panel)
        self.assertEqual([entry[0][2] for entry in canvas.texts], ["abcd"])
        self.assertEqual(panel.layout_count, 5)
        label.wrap = False
        panel.layout()
        self.assertEqual(panel.layout_count, 5)
        with self.assertRaises(TypeError):
            label.wrap = 1

    def test_typography_and_revision_update_spacing_once(self):
        class Face:
            def text_width(self, text):
                return len(text) * 9

        fonts = FontCatalog()
        face = Face()
        fonts.register("body", face, line_height=18)
        label = Label("日本語の文章", wrap=True)
        panel = Column([label], width=26, typography=Typography(fonts, "body"))
        canvas = self.draw(panel)
        self.assertEqual(label.rect.height, 54)
        self.assertEqual([entry[0][1] for entry in canvas.texts], [4, 22, 40])
        self.assertEqual(
            [entry[0][2] for entry in canvas.texts], ["日本", "語の", "文章"]
        )
        self.assertTrue(all(entry[1]["font"] is face for entry in canvas.texts))
        fonts.register("body", face, line_height=20)
        canvas = self.draw(panel)
        self.assertEqual(label.rect.height, 60)
        self.assertEqual([entry[0][1] for entry in canvas.texts], [4, 24, 44])
        self.assertEqual(panel.layout_count, 2)

    def test_idle_update_draw_does_not_rewrap_or_remeasure(self):
        class CountingFonts(FontCatalog):
            def __init__(self):
                super().__init__()
                self.wrap_calls = 0
                self.measure_calls = 0

            def wrap(self, *args):
                self.wrap_calls += 1
                return super().wrap(*args)

            def measure(self, *args):
                self.measure_calls += 1
                return super().measure(*args)

        fonts = CountingFonts()
        label = Label("A practical dialogue paragraph for a small game.", wrap=True)
        panel = Column([label], width=80, typography=Typography(fonts))
        self.draw(panel)
        counts = fonts.wrap_calls, fonts.measure_calls
        for _ in range(20):
            panel.update(UIInput())
            self.draw(panel)
        self.assertEqual((fonts.wrap_calls, fonts.measure_calls), counts)
        self.assertEqual(fonts.wrap_calls, 1)
        panel.configure(width=100)
        self.draw(panel)
        self.assertEqual(fonts.wrap_calls, 2)

    def test_explicit_height_empty_lines_and_overwide_glyph(self):
        label = Label("a\n\n", wrap=True, height=2)
        panel = Column([label], width=10, padding=4)
        canvas = self.draw(panel)
        self.assertEqual(label.rect.height, 2)
        self.assertEqual([entry[0][2] for entry in canvas.texts], ["a", "", ""])
        self.assertEqual([entry[0][1] for entry in canvas.texts], [4, 10, 16])
        label.text = ""
        label.height = None
        canvas = self.draw(panel)
        self.assertEqual(label.rect.height, 12)
        self.assertEqual([entry[0][2] for entry in canvas.texts], [""])

    def test_whitespace_collapse_is_opt_in(self):
        label = Label("one   two\tthree", wrap=True)
        panel = Column([label], width=100)
        self.assertEqual(self.draw(panel).texts[0][0][2], "one two three")
        label.wrap = False
        self.assertEqual(self.draw(panel).texts[0][0][2], "one   two\tthree")

    def test_scroll_reflow_clamps_and_updates_following_button_hits(self):
        clicks = []
        label = Label("abcdefghijklmnopqrst", wrap=True)
        button = Button("OK", lambda: clicks.append(True))
        panel = Column([label, button], width=16, viewport_height=40)
        panel.scroll_offset = 1000
        self.assertEqual(panel.scroll_offset, 52)
        canvas = self.draw(panel)
        self.assertEqual(canvas.clips[-1].height, 32)
        panel.configure(width=100)
        panel.layout()
        self.assertEqual(panel.scroll_offset, 4)
        self.assertEqual(button.rect.y, 16)
        panel.update(UIInput(10, 20, pointer_pressed=True))
        panel.update(UIInput(10, 20, pointer_released=True))
        self.assertEqual(clicks, [True])
        label.text = "short"
        panel.layout()
        self.assertEqual(label.rect.height, 12)

    def test_legacy_widget_height_override_still_used(self):
        class ExistingWidget(Widget):
            def __init__(self):
                super().__init__(height=None)

            def layout_height(self, typography):
                return 37

            def draw(self, *args, **kwargs):
                pass

        custom = ExistingWidget()
        panel = Column([custom])
        panel.layout()
        self.assertEqual(custom.rect.height, 37)
