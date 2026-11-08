"""Real JSON round trips for user-selected controls, without touching user paths."""

from tempfile import TemporaryDirectory
import unittest

from loom.input import ActionMap
from loom.storage import SaveStore


class BindingStorageTests(unittest.TestCase):
    def test_saved_rebinding_loads_into_fresh_map(self):
        actions = ActionMap({"fire": (1,), "menu": (3,)})
        actions.replace_bindings({"fire": (2,), "menu": (3,)})
        with TemporaryDirectory() as directory:
            store = SaveStore(directory, version=1)
            store.save({"bindings": actions.to_data()})
            restored = ActionMap(store.load()["bindings"])
        self.assertFalse(restored.sample(lambda key: key == 1).held)
        self.assertEqual(restored.sample(lambda key: key == 2).pressed, {"fire"})
        self.assertEqual(restored.sample(lambda key: key == 3).pressed, {"menu"})

    def test_invalid_saved_binding_does_not_destroy_live_map(self):
        actions = ActionMap({"fire": (1,)})
        actions.sample(lambda key: True)
        with TemporaryDirectory() as directory:
            store = SaveStore(directory, version=1)
            store.save({"bindings": {"fire": [True]}})
            with self.assertRaises((TypeError, ValueError)):
                actions.replace_bindings(store.load()["bindings"])
        result = actions.sample(lambda key: True)
        self.assertEqual(result.held, {"fire"})
        self.assertFalse(result.released)
        self.assertFalse(result.pressed)
