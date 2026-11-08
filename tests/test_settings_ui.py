import unittest

from loom.input import InputFrame
from loom.text import FontCatalog
from loom.ui import Column, Slider, Toggle, Typography, UIInput


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.changes = []
        self.slider = Slider("Volume", on_change=self.changes.append)
        self.panel = Column([self.slider], width=120)
        self.panel.layout()

    def point(self, fraction, **flags):
        r = self.slider.rect
        return UIInput(r.x + 5 + fraction * (r.width - 11), r.y + 8, **flags)

    def focus(self):
        self.panel.update(UIInput(next_focus=True))

    def test_toggle_release_and_confirm_change_once(self):
        toggle = Toggle("Sound", on_change=self.changes.append)
        panel = Column([toggle])
        panel.update(UIInput(10, 10, pointer_pressed=True))
        self.assertFalse(toggle.checked)
        panel.update(UIInput(10, 10, pointer_released=True, confirm=True))
        self.assertTrue(toggle.checked)
        self.assertEqual(self.changes, [True])
        panel.update(UIInput(confirm=True))
        self.assertEqual(self.changes, [True, False])

    def test_toggle_programmatic_change_and_initial_silence(self):
        toggle = Toggle("Sound", True, self.changes.append)
        toggle.checked = True
        self.assertEqual(self.changes, [])
        toggle.checked = False
        toggle.checked = False
        self.assertEqual(self.changes, [False])
        with self.assertRaises(TypeError):
            toggle.checked = 1
        with self.assertRaises(TypeError):
            Toggle("Sound", 1)

    def test_drag_is_live_and_clamped_outside(self):
        self.panel.update(self.point(0.3, pointer_pressed=True))
        self.assertAlmostEqual(self.slider.value, 0.3)
        self.panel.update(self.point(0.7))
        self.assertAlmostEqual(self.slider.value, 0.7)
        result = self.panel.update(UIInput(900, 900, pointer_released=True))
        self.assertEqual(self.slider.value, 1)
        self.assertTrue(result.pointer_consumed)
        self.panel.update(self.point(0.1))
        self.assertEqual(self.slider.value, 1)
        self.assertEqual(len(self.changes), 3)

    def test_drag_same_value_notifies_once(self):
        self.panel.update(self.point(0.3, pointer_pressed=True))
        for _ in range(10):
            self.panel.update(self.point(0.3))
        self.panel.update(self.point(0.3, pointer_released=True))
        self.assertEqual(len(self.changes), 1)

    def test_release_without_press_does_not_edit(self):
        self.panel.update(self.point(1, pointer_released=True))
        self.assertEqual(self.changes, [])

    def test_keyboard_steps_and_limits(self):
        self.focus()
        for _ in range(15):
            self.assertTrue(
                self.panel.update(UIInput(increment=True)).keyboard_consumed
            )
        self.assertEqual(self.slider.value, 1)
        self.assertEqual(len(self.changes), 10)
        for _ in range(15):
            self.panel.update(UIInput(decrement=True))
        self.assertEqual(self.slider.value, 0)
        self.assertEqual(len(self.changes), 20)

    def test_simultaneous_keys_cancel_each_other(self):
        self.focus()
        result = self.panel.update(UIInput(decrement=True, increment=True))
        self.assertTrue(result.keyboard_consumed)
        self.assertEqual(self.changes, [])

    def test_pointer_and_keyboard_same_frame_updates_once(self):
        self.panel.update(self.point(0.5, pointer_pressed=True, increment=True))
        self.assertAlmostEqual(self.slider.value, 0.5)
        self.assertEqual(len(self.changes), 1)
        self.panel.update(
            self.point(0.7, pointer_released=True, decrement=True, confirm=True)
        )
        self.assertAlmostEqual(self.slider.value, 0.7)
        self.assertEqual(len(self.changes), 2)

    def test_cancel_keeps_last_value_and_swallows_release(self):
        self.panel.update(self.point(0.5, pointer_pressed=True))
        self.panel.update(UIInput(cancel=True))
        result = self.panel.update(UIInput(900, 900, pointer_released=True))
        self.assertTrue(result.pointer_consumed)
        self.assertAlmostEqual(self.slider.value, 0.5)
        self.assertEqual(len(self.changes), 1)

    def test_reset_stops_drag_without_rollback(self):
        self.panel.update(self.point(0.5, pointer_pressed=True))
        self.panel.update(self.point(1, reset=True))
        self.panel.update(self.point(1, pointer_released=True))
        self.assertAlmostEqual(self.slider.value, 0.5)
        self.assertEqual(len(self.changes), 1)

    def test_disable_hide_or_remove_during_drag_stops_callbacks(self):
        for action in ("disable", "hide", "remove"):
            with self.subTest(action=action):
                self.setUp()
                self.panel.update(self.point(0.5, pointer_pressed=True))
                if action == "disable":
                    self.slider.enabled = False
                elif action == "hide":
                    self.slider.visible = False
                else:
                    self.panel.remove(self.slider)
                result = self.panel.update(
                    UIInput(900, 900, pointer_released=True, increment=True)
                )
                self.assertTrue(result.pointer_consumed)
                self.assertEqual(len(self.changes), 1)

    def test_callback_can_remove_slider_on_initial_press(self):
        self.slider.on_change = lambda value: self.panel.remove(self.slider)
        self.panel.update(self.point(0.5, pointer_pressed=True))
        self.assertEqual(self.panel.children, ())
        result = self.panel.update(UIInput(900, 900, pointer_released=True))
        self.assertTrue(result.pointer_consumed)

    def test_toggle_callback_can_remove_itself(self):
        toggle = Toggle("A")
        panel = Column([toggle])
        toggle.on_change = lambda checked: panel.remove(toggle)
        panel.update(UIInput(next_focus=True, confirm=True))
        self.assertEqual(panel.children, ())

    def test_nondivisible_range_reaches_both_endpoints(self):
        slider = Slider("S", minimum=-1, maximum=1, step=0.6)
        slider.value = -100
        self.assertEqual(slider.value, -1)
        for _ in range(4):
            slider.adjust(1)
        self.assertEqual(slider.value, 1)
        slider.adjust(-1)
        self.assertAlmostEqual(slider.value, 0.8)
        for _ in range(3):
            slider.adjust(-1)
        self.assertEqual(slider.value, -1)
        slider.value = 100
        self.assertEqual(slider.value, 1)

    def test_step_larger_than_range(self):
        slider = Slider("S", minimum=0, maximum=1, step=2)
        slider.adjust(1)
        self.assertEqual(slider.value, 1)
        slider.adjust(-1)
        self.assertEqual(slider.value, 0)

    def test_initial_and_programmatic_value_rules(self):
        slider = Slider("S", value=0.44, step=0.2, on_change=self.changes.append)
        self.assertAlmostEqual(slider.value, 0.4)
        self.assertEqual(self.changes, [])
        slider.value = 0.42
        self.assertEqual(self.changes, [])
        slider.value = 0.61
        self.assertAlmostEqual(self.changes[0], 0.6)
        for attr in ("minimum", "maximum", "step"):
            with self.assertRaises(AttributeError):
                setattr(slider, attr, 3)

    def test_invalid_numeric_inputs(self):
        for attr in ("minimum", "maximum", "step", "value"):
            for value in (
                float("nan"),
                float("inf"),
                float("-inf"),
                True,
                "1",
                10**1000,
            ):
                with (
                    self.subTest(attr=attr, value=value),
                    self.assertRaises(ValueError),
                ):
                    Slider("S", **{attr: value})
        for kwargs in (
            {"step": 0},
            {"step": -1},
            {"minimum": 1},
            {"maximum": -1},
            {"minimum": -1e308, "maximum": 1e308},
            {"step": 5e-324, "maximum": 1e308},
            {"minimum": 1e16, "maximum": 1e16 + 20, "step": 0.1},
            {"step": 1e-20},
        ):
            with self.assertRaises(ValueError):
                Slider("S", **kwargs)
        with self.assertRaises(ValueError):
            self.slider.value = float("nan")

    def test_typography_height_and_drawing(self):
        class Canvas:
            def __init__(self):
                self.texts = []
                self.rects = []

            def rect(self, *args):
                self.rects.append(args)

            def text(self, *args, **kwargs):
                self.texts.append(args)

        fonts = FontCatalog()
        fonts.register("body", line_height=18)
        toggle = Toggle("音声", True)
        slider = Slider("音量\n設定")
        panel = Column([toggle, slider], typography=Typography(fonts, "body"))
        canvas = Canvas()
        panel.draw(canvas)
        self.assertEqual(toggle.rect.height, 26)
        self.assertEqual(slider.rect.height, 58)
        self.assertEqual([call[2] for call in canvas.texts], ["音声", "音量", "設定"])
        self.assertTrue(all(h > 0 and w >= 0 for _, _, w, h, _ in canvas.rects))

    def test_input_mapping_is_edge_only(self):
        ui = UIInput.from_frame(
            InputFrame(pressed=frozenset({"increment", "decrement"}))
        )
        self.assertTrue(ui.increment and ui.decrement)
        held = UIInput.from_frame(
            InputFrame(held=frozenset({"increment", "decrement"}))
        )
        self.assertFalse(held.increment or held.decrement)

    def test_disabled_draw_ignores_hover_and_pressed_style(self):
        class Canvas:
            def __init__(self):
                self.calls = []

            def rect(self, *args):
                self.calls.append(args)

            def text(self, *args):
                pass

        from loom.ui import Theme

        canvas = Canvas()
        self.slider.enabled = False
        self.slider.draw(canvas, Theme(), focused=True, hovered=True, pressed=True)
        self.assertEqual(canvas.calls[0][-1], Theme().button)

    def test_confirm_does_not_preempt_slider_increment(self):
        self.focus()
        self.panel.update(UIInput(confirm=True, increment=True))
        self.assertAlmostEqual(self.slider.value, 0.1)
        self.assertEqual(len(self.changes), 1)

    def test_half_step_rounds_up_with_only_ulp_tolerance(self):
        slider = Slider("S", step=0.1)
        for value, expected in ((0.15, 0.2), (0.35, 0.4), (0.95, 1.0)):
            slider.value = value
            self.assertAlmostEqual(slider.value, expected)
            slider.value = value - 1e-8
            self.assertAlmostEqual(slider.value, expected - 0.1)
            slider.value = value + 1e-8
            self.assertAlmostEqual(slider.value, expected)
