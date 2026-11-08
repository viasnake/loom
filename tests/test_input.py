import json
import unittest

from loom.input import ActionMap


class RebindingTests(unittest.TestCase):
    def sample(self, mapping, down=()):
        return mapping.sample(set(down).__contains__)

    def test_constructor_validates_and_canonicalizes(self):
        mapping = ActionMap({"fire": [3, 1, 3], "unbound": []})
        self.assertEqual(mapping.bindings, {"fire": (1, 3), "unbound": ()})
        for data in (
            {"": [1]},
            {" ": [1]},
            {1: [1]},
            {"fire": [-1]},
            {"fire": [True]},
            {"fire": [1.0]},
            {"fire": ["1"]},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                ActionMap(data)
        with self.assertRaises(TypeError):
            ActionMap([])
        with self.assertRaises(TypeError):
            ActionMap({"fire": 1})

    def test_readonly_snapshot_and_independent_json_data(self):
        source = {"fire": [1]}
        mapping = ActionMap(source)
        source["fire"].append(2)
        snapshot = mapping.bindings
        with self.assertRaises(TypeError):
            snapshot["fire"] = (2,)
        with self.assertRaises(AttributeError):
            mapping.bindings = {}
        data = mapping.to_data()
        self.assertEqual(ActionMap(json.loads(json.dumps(data))).bindings, snapshot)
        data["fire"].append(5)
        self.assertEqual(snapshot["fire"], (1,))
        mapping.replace_bindings({"fire": [3]})
        self.assertEqual(snapshot["fire"], (1,))
        self.assertEqual(mapping.bindings["fire"], (3,))

    def test_change_cancels_once_and_blocks_down_keys_until_up(self):
        mapping = ActionMap({"fire": [1]})
        self.assertEqual(self.sample(mapping, [1]).pressed, {"fire"})
        mapping.replace_bindings({"jump": [2]})
        result = self.sample(mapping, [1, 2])
        self.assertEqual(result.released, {"fire"})
        self.assertFalse(result.held | result.pressed)
        held = self.sample(mapping, [2])
        self.assertFalse(held.held | held.pressed | held.released)
        self.assertFalse(self.sample(mapping).released)
        self.assertEqual(self.sample(mapping, [2]).pressed, {"jump"})
        self.assertEqual(self.sample(mapping).released, {"jump"})

    def test_unchanged_actions_also_cancel_on_changed_map(self):
        mapping = ActionMap({"move": [1], "fire": [2]})
        self.sample(mapping, [1, 2])
        mapping.replace_bindings({"move": [1], "fire": [3]})
        result = self.sample(mapping, [1, 3])
        self.assertEqual(result.released, {"move", "fire"})
        self.assertFalse(result.held)
        self.assertFalse(self.sample(mapping, [1, 3]).held)
        self.sample(mapping, [])
        self.assertEqual(self.sample(mapping, [1, 3]).pressed, {"move", "fire"})

    def test_equal_map_is_noop_even_reordered_and_duplicated(self):
        mapping = ActionMap({"fire": [1, 2]})
        self.sample(mapping, [1])
        snapshot = mapping.bindings
        mapping.replace_bindings({"fire": [2, 1, 1]})
        self.assertIs(mapping.bindings, snapshot)
        result = self.sample(mapping, [1])
        self.assertEqual(result.held, {"fire"})
        self.assertFalse(result.pressed | result.released)

    def test_invalid_replacement_is_atomic_including_held_state(self):
        mapping = ActionMap({"fire": [1]})
        self.sample(mapping, [1])
        snapshot = mapping.bindings
        with self.assertRaises(ValueError):
            mapping.replace_bindings({"valid": [2], "invalid": [False]})
        self.assertIs(mapping.bindings, snapshot)
        result = self.sample(mapping, [1])
        self.assertEqual(result.held, {"fire"})
        self.assertFalse(result.pressed | result.released)

    def test_multiple_replacements_keep_original_cancellation(self):
        mapping = ActionMap({"fire": [1]})
        self.sample(mapping, [1])
        mapping.replace_bindings({"jump": [2]})
        mapping.replace_bindings({"move": [3]})
        mapping.replace_bindings({"move": [3, 3]})
        result = self.sample(mapping, [3])
        self.assertEqual(result.released, {"fire"})
        self.assertFalse(result.held)
        self.assertFalse(self.sample(mapping, [3]).released)

    def test_alternate_up_key_can_press_while_other_key_is_suppressed(self):
        mapping = ActionMap({})
        mapping.replace_bindings({"fire": [1, 2], "alias": [1]})
        self.sample(mapping, [1])
        result = self.sample(mapping, [1, 2])
        self.assertEqual(result.pressed, {"fire"})
        self.assertEqual(self.sample(mapping, [1]).released, {"fire"})
        self.sample(mapping, [])
        self.assertEqual(self.sample(mapping, [1]).pressed, {"fire", "alias"})

    def test_reset_preserves_pending_cancel_and_suppression(self):
        mapping = ActionMap({"fire": [1]})
        self.sample(mapping, [1])
        mapping.replace_bindings({"jump": [2]})
        mapping.reset()
        result = self.sample(mapping, [2])
        self.assertEqual(result.released, {"fire"})
        self.assertFalse(result.held)
        mapping.reset()
        self.assertFalse(self.sample(mapping, [2]).held)
        self.sample(mapping, [])
        self.assertEqual(self.sample(mapping, [2]).pressed, {"jump"})

    def test_empty_replacement_cancels_actions(self):
        mapping = ActionMap({"fire": [1]})
        self.sample(mapping, [1])
        mapping.replace_bindings({})
        self.assertEqual(self.sample(mapping, [1]).released, {"fire"})
        self.assertFalse(self.sample(mapping, [1]).held)

    def test_each_unique_key_polled_once_and_metadata_preserved(self):
        mapping = ActionMap({"fire": [1, 2], "alias": [1]})
        mapping.replace_bindings({"jump": [2, 3], "alias": [2]})
        calls = []

        def poll(key):
            calls.append(key)
            return True

        result = mapping.sample(poll, pointer=(3, 4), world_pointer=(1, 2), wheel=5)
        self.assertEqual(sorted(calls), [2, 3])
        self.assertEqual(
            (result.pointer, result.world_pointer, result.wheel), ((3, 4), (1, 2), 5)
        )

    def test_rebinding_validation_has_no_polling_side_effect(self):
        mapping = ActionMap({"fire": [1]})
        mapping.replace_bindings({"jump": [2]})
        # The first sample, not replacement time, determines held-key suppression.
        self.assertFalse(self.sample(mapping, [2]).pressed)

    def test_key_collections_reject_text_bytes_and_mappings(self):
        for codes in ("", "12", b"", b"12", bytearray([1, 2]), {}, {1: True}):
            with self.subTest(codes=codes), self.assertRaises(TypeError):
                ActionMap({"fire": codes})
        self.assertEqual(ActionMap({"fire": ()}).bindings["fire"], ())
        self.assertEqual(ActionMap({"fire": iter([2, 1, 2])}).bindings["fire"], (1, 2))

    def test_invalid_collection_replacement_retains_snapshot(self):
        mapping = ActionMap({"fire": [1]})
        snapshot = mapping.bindings
        with self.assertRaises(TypeError):
            mapping.replace_bindings({"new": [2], "bad": b"12"})
        self.assertIs(mapping.bindings, snapshot)

    def test_cancelled_distinguishes_rebind_from_real_release(self):
        mapping = ActionMap({"primary": [1], "move": [2]})
        self.sample(mapping, [1, 2])
        mapping.replace_bindings({"primary": [3]})
        cancelled = self.sample(mapping, [3])
        self.assertEqual(cancelled.cancelled, {"primary", "move"})
        self.assertEqual(cancelled.released, cancelled.cancelled)
        filtered = cancelled.without({"primary"})
        self.assertEqual(filtered.cancelled, {"move"})
        self.assertEqual(filtered.released, {"move"})
        self.assertFalse(self.sample(mapping, [3]).cancelled)
        self.sample(mapping, [])
        self.sample(mapping, [3])
        real_release = self.sample(mapping, [])
        self.assertEqual(real_release.released, {"primary"})
        self.assertFalse(real_release.cancelled)
