import unittest

from loom.input import InputFrame
from loom.routing import UIRouter
from loom.ui import Button, Column


def frame(*, held=(), pressed=(), released=(), pointer=(10, 10), wheel=0):
    return InputFrame(
        frozenset(held), frozenset(pressed), frozenset(released), pointer, wheel=wheel
    )


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.clicks = []
        self.back = Column([Button("back", lambda: self.clicks.append("back"))])
        self.front = Column([Button("front", lambda: self.clicks.append("front"))])
        self.router = UIRouter([self.back, self.front])

    def click(self, pointer=(10, 10)):
        self.router.update(
            frame(held=["primary"], pressed=["primary"], pointer=pointer)
        )
        return self.router.update(frame(released=["primary"], pointer=pointer))

    def test_only_front_activates_and_edges_stay_hidden(self):
        result = self.click()
        self.assertEqual(self.clicks, ["front"])
        self.assertFalse(result.remaining.released)
        self.assertIs(self.router.active, self.front)

    def test_drag_stays_with_original_panel_after_reorder(self):
        self.router.update(frame(held=["primary"], pressed=["primary"]))
        self.router.bring_to_front(self.back)
        self.router.update(frame(released=["primary"]))
        self.assertEqual(self.clicks, ["front"])

    def test_removed_capture_swallows_release(self):
        self.router.update(frame(held=["primary"], pressed=["primary"]))
        self.router.remove(self.front)
        result = self.router.update(frame(released=["primary"]))
        self.assertFalse(result.remaining.released)
        self.assertEqual(self.clicks, [])
        self.click()
        self.assertEqual(self.clicks, ["back"])

    def test_callback_removal_is_safe(self):
        self.front.children[0].on_click = lambda: self.router.remove(self.front)
        self.click()
        self.assertEqual(self.router.panels, (self.back,))

    def test_confirm_held_is_blocked_until_release(self):
        self.router.update(frame(pressed=["next"], held=["next"]))
        self.router.update(frame(released=["next"]))
        first = self.router.update(frame(pressed=["confirm"], held=["confirm"]))
        held = self.router.update(frame(held=["confirm"]))
        release = self.router.update(frame(released=["confirm"]))
        self.assertEqual(self.clicks, ["front"])
        self.assertFalse(
            first.remaining.pressed | held.remaining.held | release.remaining.released
        )
        self.router.remove(self.front)
        self.router.remove(self.back)
        fresh = self.router.update(frame(pressed=["confirm"], held=["confirm"]))
        self.assertIn("confirm", fresh.remaining.pressed)

    def test_game_owned_release_not_stolen_by_hover(self):
        start = self.router.update(
            frame(held=["primary"], pressed=["primary"], pointer=(500, 500))
        )
        self.assertIn("primary", start.remaining.pressed)
        held = self.router.update(frame(held=["primary"]))
        release = self.router.update(frame(released=["primary"]))
        self.assertFalse(held.pointer_consumed)
        self.assertFalse(release.pointer_consumed)
        self.assertIn("primary", held.remaining.held)
        self.assertIn("primary", release.remaining.released)
        self.assertEqual(self.clicks, [])

    def test_modal_cancels_game_once_and_does_not_revive_hold(self):
        self.router.update(frame(held=["move"], pressed=["move"], pointer=(500, 500)))
        self.front.modal = True
        result = self.router.update(frame(held=["move"]))
        self.assertEqual(result.remaining.released, frozenset({"move"}))
        self.assertFalse(self.router.update(frame(held=["move"])).remaining.released)
        self.front.modal = False
        self.assertFalse(self.router.update(frame(held=["move"])).remaining.held)
        self.assertFalse(
            self.router.update(frame(released=["move"])).remaining.released
        )
        self.assertIn(
            "move",
            self.router.update(
                frame(held=["move"], pressed=["move"])
            ).remaining.pressed,
        )

    def test_open_modal_callback_blocks_current_frame(self):
        modal = Column(modal=True)
        self.front.children[0].on_click = lambda: self.router.add(modal)
        self.router.update(frame(held=["primary"], pressed=["primary"]))
        result = self.router.update(
            frame(released=["primary"], pressed=["jump"], held=["jump"])
        )
        self.assertFalse(result.remaining.held | result.remaining.pressed)

    def test_close_modal_callback_still_blocks_frame(self):
        self.front.modal = True
        self.front.children[0].on_click = lambda: self.router.remove(self.front)
        self.router.update(frame(held=["primary"], pressed=["primary"]))
        result = self.router.update(
            frame(released=["primary"], pressed=["jump"], held=["jump"])
        )
        self.assertFalse(result.remaining.held | result.remaining.pressed)

    def test_alias_groups_block_only_explicit_aliases(self):
        router = UIRouter([self.front], pointer_actions={"primary", "fire"})
        result = router.update(
            frame(held=["primary", "fire", "move"], pressed=["primary", "fire", "move"])
        )
        self.assertEqual(result.remaining.held, frozenset({"move"}))
        self.assertFalse(router.update(frame(held=["primary", "fire"])).remaining.held)
        with self.assertRaises(ValueError):
            UIRouter(pointer_actions={"confirm"})

    def test_reset_cancels_once_and_blocks_still_held(self):
        self.router.update(frame(held=["move"], pressed=["move"]))
        result = self.router.update(frame(held=["move"]), reset=True)
        self.assertEqual(result.remaining.released, frozenset({"move"}))
        self.assertFalse(self.router.update(frame(held=["move"])).remaining.held)

    def test_wheel_and_original_frame_are_independent(self):
        original = frame(wheel=2)
        result = self.router.update(original)
        self.assertEqual(original.wheel, 2)
        self.assertEqual(result.remaining.wheel, 0)
        self.assertEqual(
            self.router.update(frame(pointer=(500, 500), wheel=2)).remaining.wheel, 2
        )

    def test_modal_blocks_back_even_when_pointer_misses_modal(self):
        self.front.configure(x=300)
        self.front.modal = True
        self.click()
        self.assertEqual(self.clicks, [])

    def test_up_snapshot_without_release_clears_ownership(self):
        self.router.update(frame(held=["primary"], pressed=["primary"]))
        self.router.update(frame(pointer=(500, 500)))
        result = self.router.update(
            frame(held=["primary"], pressed=["primary"], pointer=(500, 500))
        )
        self.assertIn("primary", result.remaining.pressed)
        self.router.update(frame())
        self.router.update(frame(held=["move"], pressed=["move"]))
        self.router.update(frame(held=["move"]), reset=True)
        self.router.update(frame())
        self.assertIn(
            "move",
            self.router.update(
                frame(held=["move"], pressed=["move"])
            ).remaining.pressed,
        )


class RoutingConfigurationTests(unittest.TestCase):
    def test_builtin_actions_are_always_included_with_aliases(self):
        aliases = ["fire"]
        router = UIRouter(pointer_actions=aliases, navigation_actions=["charge"])
        aliases.append("later")
        self.assertEqual(router.pointer_actions, {"primary", "fire"})
        self.assertEqual(
            router.navigation_actions,
            {
                "confirm",
                "cancel",
                "next",
                "previous",
                "decrement",
                "increment",
                "charge",
            },
        )
        panel = Column([Button("UI", lambda: None)])
        router.add(panel)
        result = router.update(
            frame(held=["primary", "fire"], pressed=["primary", "fire"])
        )
        self.assertFalse(result.remaining.held)
        self.assertFalse(result.remaining.pressed)

    def test_invalid_alias_collections_are_rejected(self):
        for aliases in ("fire", b"fire"):
            with self.assertRaises(TypeError):
                UIRouter(pointer_actions=aliases)
            with self.assertRaises(TypeError):
                UIRouter(navigation_actions=aliases)
        for aliases in ([""], ["   "], [1]):
            with self.assertRaises(ValueError):
                UIRouter(pointer_actions=aliases)
        with self.assertRaises(ValueError):
            UIRouter(pointer_actions={"confirm"})


class SettingsRoutingTests(unittest.TestCase):
    def test_adjustment_reaches_only_active_panel_and_blocks_game_alias(self):
        from loom.ui import Slider

        back = Slider("Back", value=0.5)
        front = Slider("Front", value=0.5)
        router = UIRouter(
            [Column([back]), Column([front])], navigation_actions={"right"}
        )
        router.update(frame(pressed=["next"]))
        result = router.update(
            frame(held=["increment", "right"], pressed=["increment", "right"])
        )
        self.assertAlmostEqual(front.value, 0.6)
        self.assertEqual(back.value, 0.5)
        self.assertFalse(result.remaining.pressed)
        self.assertFalse(result.remaining.held)
        released = router.update(frame(released=["increment", "right"]))
        self.assertFalse(released.remaining.released)

    def test_slider_drag_survives_leaving_panel_but_not_removal(self):
        from loom.ui import Slider

        changes = []
        slider = Slider("Volume", value=0.5, on_change=changes.append)
        panel = Column([slider], width=100)
        router = UIRouter([panel], pointer_actions={"fire"})
        router.update(frame(held=["primary", "fire"], pressed=["primary", "fire"]))
        result = router.update(frame(held=["primary", "fire"], pointer=(500, 10)))
        self.assertEqual(slider.value, slider.maximum)
        self.assertFalse(result.remaining.held)
        router.remove(panel)
        count = len(changes)
        result = router.update(frame(released=["primary", "fire"], pointer=(-100, 10)))
        self.assertEqual(len(changes), count)
        self.assertFalse(result.remaining.released)

    def test_up_resync_stops_drag_before_new_coordinates_are_applied(self):
        from loom.ui import Slider

        slider = Slider("Volume", value=0.5)
        router = UIRouter([Column([slider], width=100)])
        router.update(frame(held=["primary"], pressed=["primary"], pointer=(40, 10)))
        value = slider.value
        router.update(frame(pointer=(500, 10)))
        self.assertEqual(slider.value, value)
