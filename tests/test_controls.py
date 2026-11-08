import json
import unittest

from loom.controls import BindingEditor, CaptureResult, KeyCapture
from loom.input import ActionMap


class BindingEditorTests(unittest.TestCase):
    def setUp(self):
        self.defaults = {"jump": [1, 2], "fire": [3], "menu": [4]}
        self.editor = BindingEditor(self.defaults)

    def test_readonly_independent_snapshots_and_data(self):
        snapshot = self.editor.bindings
        self.defaults["jump"].append(99)
        with self.assertRaises(TypeError):
            snapshot["jump"] = ()
        with self.assertRaises(AttributeError):
            self.editor.bindings = {}
        self.editor.assign("jump", [9])
        self.assertEqual(snapshot["jump"], (1, 2))
        data = self.editor.to_data()
        self.assertEqual(
            BindingEditor(self.defaults, json.loads(json.dumps(data))).bindings,
            self.editor.bindings,
        )
        data["jump"].append(99)
        self.assertEqual(self.editor.bindings["jump"], (9,))
        self.assertEqual(self.editor.defaults["jump"], (1, 2))

    def test_conflicts_inspection_and_reject_are_nonmutating(self):
        original = self.editor.bindings
        self.assertEqual(
            self.editor.conflicts("jump", [3, 4, 3]), {"fire": (3,), "menu": (4,)}
        )
        with self.assertRaisesRegex(ValueError, "fire, menu"):
            self.editor.assign("jump", [3, 4])
        self.assertIs(self.editor.bindings, original)

    def test_share_then_reassign_removes_every_other_owner(self):
        self.editor.assign("jump", [3], conflict="share")
        self.assertEqual(self.editor.bindings["fire"], (3,))
        self.editor.assign("menu", [3], conflict="reassign")
        self.assertEqual(self.editor.bindings, {"jump": (), "fire": (), "menu": (3,)})

    def test_reassign_retains_unrelated_keys(self):
        self.editor.assign("fire", [2, 4], conflict="reassign")
        self.assertEqual(
            self.editor.bindings, {"jump": (1,), "fire": (2, 4), "menu": ()}
        )

    def test_clear_and_restore_all_defaults(self):
        self.editor.clear("jump")
        self.editor.assign("fire", [9])
        self.assertEqual(self.editor.bindings["jump"], ())
        self.editor.restore_defaults()
        self.assertEqual(
            self.editor.bindings, {"jump": (1, 2), "fire": (3,), "menu": (4,)}
        )

    def test_invalid_operations_are_atomic(self):
        original = self.editor.bindings
        for keys in ([True], [-1], [1.5], ["1"]):
            with self.assertRaises(ValueError):
                self.editor.assign("jump", keys, conflict="reassign")
        for keys in ("", b"12", {1: True}):
            with self.assertRaises(TypeError):
                self.editor.assign("jump", keys)
        with self.assertRaises(KeyError):
            self.editor.assign("unknown", [1])
        with self.assertRaises(KeyError):
            self.editor.clear("unknown")
        with self.assertRaises(ValueError):
            self.editor.assign("jump", [9], conflict="typo")
        self.assertIs(self.editor.bindings, original)

    def test_loaded_action_names_must_match_defaults(self):
        with self.assertRaises(ValueError):
            BindingEditor(self.defaults, {"jump": [9]})
        with self.assertRaises(ValueError):
            BindingEditor(self.defaults, {**self.defaults, "extra": [5]})

    def test_draft_changes_do_not_change_live_mapping(self):
        live = ActionMap(self.editor.bindings)
        self.editor.assign("jump", [9])
        self.assertEqual(live.bindings["jump"], (1, 2))
        live.replace_bindings(self.editor.bindings)
        self.assertEqual(live.bindings["jump"], (9,))


class KeyCaptureTests(unittest.TestCase):
    def setUp(self):
        self.capture = KeyCapture()

    def test_idle_and_cancel_idle_do_nothing(self):
        self.assertEqual(self.capture.update([1]), CaptureResult())
        self.assertEqual(self.capture.cancel(), CaptureResult())

    def test_opener_held_is_ignored_until_release_and_new_press(self):
        self.capture.begin("jump", [1])
        self.assertEqual(self.capture.update([1]).status, "waiting")
        self.assertEqual(self.capture.update([]).status, "waiting")
        self.assertEqual(self.capture.update([1]), CaptureResult("jump", "captured", 1))

    def test_fresh_key_can_capture_while_opener_remains_down(self):
        self.capture.begin("jump", [1])
        self.assertEqual(
            self.capture.update([1, 9]), CaptureResult("jump", "captured", 9)
        )

    def test_ambiguity_waits_for_all_up_then_retries(self):
        self.capture.begin("jump")
        ambiguous = self.capture.update([4, 3, 4])
        self.assertEqual(
            ambiguous, CaptureResult("jump", "ambiguous", candidates=(3, 4))
        )
        self.assertEqual(self.capture.update([4]), ambiguous)
        self.assertEqual(self.capture.update([4, 5]), ambiguous)
        self.assertEqual(self.capture.update([]).status, "waiting")
        self.assertEqual(self.capture.update([8]), CaptureResult("jump", "captured", 8))

    def test_cancel_before_update_wins_and_is_terminal(self):
        self.capture.begin("fire")
        cancelled = self.capture.cancel()
        self.assertEqual(cancelled, CaptureResult("fire", "cancelled"))
        self.assertEqual(self.capture.update([2]), cancelled)
        self.capture.begin("menu")
        self.assertEqual(self.capture.update([4]), CaptureResult("menu", "captured", 4))

    def test_success_is_terminal_until_begin(self):
        self.capture.begin("fire")
        captured = self.capture.update([2])
        self.assertIs(self.capture.update([3]), captured)
        self.assertIs(self.capture.cancel(), captured)
        self.capture.begin("jump", [3])
        self.assertEqual(self.capture.update([3]).status, "waiting")

    def test_invalid_begin_or_update_preserves_state(self):
        self.capture.begin("fire", [1])
        result = self.capture.result
        with self.assertRaises(ValueError):
            self.capture.begin(" ", [])
        for bad in ([True], [-1], [1.5]):
            with self.assertRaises(ValueError):
                self.capture.update(bad)
        with self.assertRaises(TypeError):
            self.capture.begin("jump", b"12")
        self.assertIs(self.capture.result, result)
        self.assertEqual(self.capture.update([1]).status, "waiting")

    def test_capture_uses_actionmap_snapshot_without_extra_poll(self):
        live = ActionMap({"menu": [1]}, watched_keys=[1, 2, 3])
        calls = []

        def down(code):
            calls.append(code)
            return code in (1, 3)

        live.sample(down)
        self.capture.begin("jump", live.physical_held)
        calls.clear()
        live.sample(lambda key: calls.append(key) or key == 2)
        result = self.capture.update(live.physical_held)
        self.assertEqual(result.key, 2)
        self.assertEqual(sorted(calls), [1, 2, 3])
