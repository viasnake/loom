import unittest

from loom import ActionRepeat, Button, Column, InputFrame, Slider, UIRouter


def frame(*, held=(), pressed=(), released=(), cancelled=(), pointer=(500, 500)):
    return InputFrame(
        frozenset(held),
        frozenset(pressed),
        frozenset(released),
        pointer,
        cancelled=frozenset(cancelled),
    )


class ActionRepeatTests(unittest.TestCase):
    def test_delay_interval_variable_time_and_no_catchup_burst(self):
        repeat = ActionRepeat(["next"], delay=0.5, interval=0.125)
        press = frame(held=["next"], pressed=["next"])
        held = frame(held=["next"])
        self.assertEqual(repeat.update(press, 10), {"next"})
        self.assertFalse(repeat.update(held, 0.25))
        self.assertEqual(repeat.update(held, 0.25), {"next"})
        self.assertEqual(repeat.update(held, 100), {"next"})
        self.assertFalse(repeat.update(held, 0))
        self.assertFalse(repeat.update(held, 0.0625))
        self.assertEqual(repeat.update(held, 0.0625), {"next"})
        self.assertEqual(press.pressed, {"next"})
        self.assertFalse(held.pressed)

    def test_only_selected_fresh_press_arms_release_cancel_and_up_snapshot_stop(self):
        repeat = ActionRepeat(["next"])
        held = frame(held=["next"])
        self.assertFalse(repeat.update(held, 100))
        self.assertFalse(repeat.update(frame(pressed=["confirm"]), 0))
        for stop in (
            frame(),
            frame(released=["next"]),
            frame(held=["next"], cancelled=["next"]),
        ):
            self.assertEqual(
                repeat.update(frame(held=["next"], pressed=["next"]), 0), {"next"}
            )
            self.assertFalse(repeat.update(stop, 0))
            self.assertFalse(repeat.update(held, 100))
        repeat.update(frame(held=["next"], pressed=["next"]), 0)
        repeat.reset()
        self.assertFalse(repeat.update(held, 100))
        self.assertFalse(
            repeat.update(frame(held=["next"], pressed=["next"]), 0, reset=True)
        )
        self.assertFalse(repeat.update(held, 100))

    def test_completed_pulse_does_not_arm_and_independent_actions(self):
        repeat = ActionRepeat(["next", "increment"])
        self.assertEqual(
            repeat.update(frame(held=["next"], pressed=["next"], released=["next"]), 0),
            {"next"},
        )
        self.assertFalse(repeat.update(frame(held=["next"]), 1))
        self.assertEqual(
            repeat.update(
                frame(held=["next", "increment"], pressed=["next", "increment"]), 0
            ),
            {"next", "increment"},
        )
        self.assertEqual(
            repeat.update(frame(held=["increment"], released=["next"]), 1),
            {"increment"},
        )

    def test_validation_is_atomic_and_configuration_is_readonly(self):
        for value in (0, -1, True, float("nan"), float("inf"), 10**1000, "1"):
            with self.assertRaises(ValueError):
                ActionRepeat(["next"], delay=value)
            with self.assertRaises(ValueError):
                ActionRepeat(["next"], interval=value)
        for names in ([""], [1], "next"):
            with self.assertRaises((TypeError, ValueError)):
                ActionRepeat(names)
        repeat = ActionRepeat(["next"], delay=0.5)
        with self.assertRaises(AttributeError):
            repeat.actions = {"confirm"}
        repeat.update(frame(held=["next"], pressed=["next"]), 0)
        for dt in (-1, True, float("inf"), float("nan"), 10**1000):
            with self.assertRaises(ValueError):
                repeat.update(frame(), dt)
        self.assertEqual(repeat.update(frame(held=["next"]), 0.5), {"next"})


class RouterRepeatTests(unittest.TestCase):
    def setUp(self):
        self.buttons = [Button(str(i), lambda: None) for i in range(10)]
        self.panel = Column(self.buttons, viewport_height=60)
        self.router = UIRouter(
            [self.panel],
            repeat=ActionRepeat(["next", "increment"], delay=0.5, interval=0.125),
        )

    def test_hold_moves_focus_scrolls_and_does_not_forge_game_edges(self):
        first = self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
        self.assertTrue(first.keyboard_consumed)
        for _ in range(7):
            result = self.router.update(frame(held=["next"]), dt=0.5)
            self.assertFalse(result.remaining.pressed)
        self.assertGreater(self.panel.scroll_offset, 0)

    def test_slider_repeats_but_confirm_never_repeats(self):
        values, clicks = [], []
        slider = Slider("volume", value=0, step=0.1, on_change=values.append)
        panel = Column([slider, Button("buy", lambda: clicks.append(1))])
        router = UIRouter([panel], repeat=ActionRepeat(["increment"]))
        router.update(frame(pressed=["next"]), dt=0)
        router.update(frame(pressed=["increment"], held=["increment"]), dt=0)
        router.update(frame(held=["increment"]), dt=0.5)
        self.assertEqual(len(values), 2)
        router.update(frame(pressed=["next"]), dt=0)
        router.update(frame(pressed=["confirm"], held=["confirm"]), dt=0)
        router.update(frame(held=["confirm"]), dt=10)
        self.assertEqual(clicks, [1])

    def test_modal_change_and_removal_require_new_press(self):
        self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
        modal = Column([Button("modal", lambda: None)], modal=True)
        self.router.add(modal)
        self.router.update(frame(held=["next"]), dt=10)
        self.assertIsNone(modal.focused)
        self.router.remove(modal)
        offset = self.panel.scroll_offset
        self.router.update(frame(held=["next"]), dt=10)
        self.router.update(frame(held=["next"]), dt=10)
        self.assertEqual(self.panel.scroll_offset, offset)
        self.router.update(frame(), dt=0)
        self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
        self.assertTrue(
            self.router.update(frame(held=["next"]), dt=0.5).keyboard_consumed
        )

    def test_context_change_press_works_once_but_does_not_arm_repeat(self):
        self.router.update(frame(), dt=0)
        modal = Column([Button(str(i), lambda: None) for i in range(3)], modal=True)
        self.router.add(modal)
        self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
        focus = modal.focused
        self.assertIsNotNone(focus)
        self.router.update(frame(held=["next"]), dt=10)
        self.assertIs(modal.focused, focus)

    def test_explicit_reset_cancel_and_invalid_dt(self):
        for reset_frame, reset in (
            (frame(held=["next"]), True),
            (frame(held=["next"], cancelled=["next"]), False),
        ):
            self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
            self.router.update(reset_frame, dt=0.5, reset=reset)
            self.assertFalse(
                self.router.update(frame(held=["next"]), dt=10).keyboard_consumed
            )
        for dt in (None, -1, float("nan")):
            with self.assertRaises(ValueError):
                self.router.update(frame(pressed=["next"]), dt=dt)
        for action in ("confirm", "primary", "cancel", "purchase"):
            with self.assertRaises(ValueError):
                UIRouter(repeat=ActionRepeat([action]))
        UIRouter().update(frame())  # Original API does not require dt.

    def test_ignored_press_cannot_later_repeat_into_same_panel(self):
        panel = Column([])
        router = UIRouter([panel], repeat=ActionRepeat(["next"]))
        result = router.update(frame(held=["next"], pressed=["next"]), dt=0)
        self.assertEqual(result.remaining.pressed, {"next"})
        panel.add(Button("added later", lambda: None))
        router.update(frame(held=["next"]), dt=10)
        self.assertIsNone(panel.focused)
        router.update(frame(released=["next"]), dt=0)
        router.update(frame(held=["next"], pressed=["next"]), dt=0)
        self.assertIsNotNone(panel.focused)

    def test_opposite_holds_cancel_repeat_until_fresh_press(self):
        panel = Column([Button(str(i), lambda: None) for i in range(3)])
        router = UIRouter([panel], repeat=ActionRepeat(["next", "previous"]))
        router.update(frame(held=["next"], pressed=["next"]), dt=0)
        router.update(frame(held=["next", "previous"], pressed=["previous"]), dt=0.5)
        focus = panel.focused
        router.update(frame(held=["next", "previous"]), dt=10)
        self.assertIs(panel.focused, focus)
        router.update(frame(held=["next"], released=["previous"]), dt=10)
        self.assertIs(panel.focused, focus)

    def test_ambiguous_multi_action_press_does_not_arm(self):
        panel = Column([Button(str(i), lambda: None) for i in range(3)])
        router = UIRouter([panel], repeat=ActionRepeat(["next", "increment"]))
        router.update(
            frame(held=["next", "increment"], pressed=["next", "increment"]), dt=0
        )
        focus = panel.focused
        router.update(frame(held=["next", "increment"]), dt=10)
        self.assertIs(panel.focused, focus)

    def test_cancel_button_and_pointer_panel_change_discard_repeat(self):
        self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
        self.router.update(frame(held=["next"], pressed=["cancel"]), dt=0)
        self.assertFalse(
            self.router.update(frame(held=["next"]), dt=10).keyboard_consumed
        )
        other = Column([Button(str(i), lambda: None) for i in range(3)], x=200)
        self.router.add(other)
        self.router.update(frame(held=["next"], pressed=["next"]), dt=0)
        self.router.update(
            frame(held=["next", "primary"], pressed=["primary"], pointer=(210, 10)),
            dt=0,
        )
        focus = other.focused
        self.router.update(
            frame(held=["next"], released=["primary"], pointer=(210, 10)), dt=1
        )
        self.router.update(frame(held=["next"]), dt=10)
        self.assertIs(other.focused, focus)

    def test_adjustment_does_not_cross_slider_focus_but_navigation_continues(self):
        first, second = Slider("one", value=0, step=0.1), Slider(
            "two", value=0, step=0.1
        )
        panel = Column([first, second])
        router = UIRouter([panel], repeat=ActionRepeat(["increment", "next"]))
        router.update(frame(pressed=["next"]), dt=0)
        router.update(frame(held=["increment"], pressed=["increment"]), dt=0)
        self.assertEqual(first.value, 0.1)
        router.update(frame(held=["increment", "next"], pressed=["next"]), dt=0.5)
        router.update(frame(held=["increment", "next"]), dt=0.5)
        self.assertEqual(second.value, 0)
        self.assertIs(panel.focused, first)  # Navigation repeat is not cancelled.
        router.update(frame(held=["increment"]), dt=1)
        self.assertEqual(first.value, 0.1)

    def test_pointer_focus_change_does_not_receive_due_adjustment(self):
        first, second = Slider("one", value=0, step=0.1), Slider(
            "two", value=0, step=0.1
        )
        panel = Column([first, second])
        router = UIRouter([panel], repeat=ActionRepeat(["increment"]))
        router.update(frame(pressed=["next"]), dt=0)
        router.update(frame(held=["increment"], pressed=["increment"]), dt=0)
        router.update(
            frame(
                held=["increment", "primary"],
                pressed=["primary"],
                pointer=(second.rect.x + 5, second.rect.y + 1),
            ),
            dt=0.5,
        )
        self.assertIs(panel.focused, second)
        self.assertEqual(second.value, 0)
