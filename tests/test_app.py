import unittest
from loom import Scene, SceneStack, InputFrame, ActionMap


class Probe(Scene):
    def __init__(self):
        self.events = []
        self.frames = []

    def enter(self, stack):
        super().enter(stack)
        self.events.append("enter")

    def exit(self):
        self.events.append("exit")

    def pause(self):
        self.events.append("pause")

    def resume(self):
        self.events.append("resume")

    def update(self, frame, dt):
        self.frames.append(frame)

    def draw(self, target):
        target.append(self)


class SceneTests(unittest.TestCase):
    def test_modal_blocks_input_and_update(self):
        root = Probe()
        stack = SceneStack(root)
        modal = Probe()
        stack.push(modal)
        stack.update(InputFrame(), 0.1)
        stack.update(InputFrame(pressed=frozenset({"confirm"})), 0.1)
        self.assertEqual(len(root.frames), 1)
        self.assertIn("confirm", modal.frames[0].pressed)
        stack.pop()
        stack.update(InputFrame(), 0.1)
        self.assertEqual(root.events, ["enter", "pause", "resume"])
        self.assertEqual(modal.events, ["enter", "exit"])

    def test_lower_scene_updates_without_input(self):
        root = Probe()
        modal = Probe()
        modal.blocks_update_below = False
        modal.opaque = False
        stack = SceneStack(root)
        stack.push(modal)
        stack.update(InputFrame(), 0)
        stack.update(InputFrame(pressed=frozenset({"confirm"})), 0.1)
        self.assertFalse(root.frames[-1].pressed)
        drawn = []
        stack.draw(drawn)
        self.assertEqual(drawn, [root, modal])

    def test_conflicting_requests_and_root_pop(self):
        stack = SceneStack(Probe())
        with self.assertRaises(RuntimeError):
            stack.pop()
        stack.push(Probe())
        with self.assertRaises(RuntimeError):
            stack.replace(Probe())

    def test_replace_and_cleanup(self):
        a = Probe()
        b = Probe()
        stack = SceneStack(a)
        stack.replace(b)
        stack.update(InputFrame(), 0)
        stack.close()
        self.assertEqual(a.events, ["enter", "exit"])
        self.assertEqual(b.events, ["enter", "exit"])

    def test_actions_edges_and_shared_key(self):
        actions = ActionMap({"confirm": (1, 2), "other": (1,)})
        calls = []
        f = actions.sample(lambda k: calls.append(k) or k == 1)
        self.assertEqual(calls, [1, 2])
        self.assertEqual(f.pressed, {"confirm", "other"})
        self.assertFalse(actions.sample(lambda k: k == 1).pressed)
        self.assertEqual(actions.sample(lambda k: False).released, {"confirm", "other"})

    def test_reset_suppresses_held_press(self):
        actions = ActionMap({"confirm": (1,)})
        actions.sample(lambda key: True)
        actions.reset()
        self.assertFalse(actions.sample(lambda key: True).pressed)
        actions.sample(lambda key: False)
        self.assertEqual(actions.sample(lambda key: True).pressed, {"confirm"})


class LifecycleTests(unittest.TestCase):
    def test_close_attempts_every_exit_and_is_idempotent(self):
        class Broken(Probe):
            def exit(self):
                super().exit()
                raise ValueError("cleanup")

        root, modal = Probe(), Broken()
        stack = SceneStack(root)
        stack.push(modal)
        stack.update(InputFrame(), 0)
        with self.assertRaises(ExceptionGroup):
            stack.close()
        stack.close()
        self.assertEqual(root.events.count("exit"), 1)
        self.assertEqual(modal.events.count("exit"), 1)
        with self.assertRaisesRegex(RuntimeError, "closed"):
            stack.push(Probe())
        with self.assertRaisesRegex(RuntimeError, "closed"):
            stack.update(InputFrame(), 0)

    def test_initial_enter_failure_cleans_up(self):
        class Broken(Probe):
            def enter(self, stack):
                super().enter(stack)
                raise ValueError("initialization")

        scene = Broken()
        with self.assertRaisesRegex(ValueError, "initialization"):
            SceneStack(scene)
        self.assertEqual(scene.events, ["enter", "exit"])

    def test_initialization_and_cleanup_errors_preserved(self):
        class Broken(Scene):
            def enter(self, stack):
                raise ValueError("initialization")

            def exit(self):
                raise OSError("cleanup")

        with self.assertRaises(ExceptionGroup) as caught:
            SceneStack(Broken())
        self.assertIsInstance(caught.exception.exceptions[0], ValueError)
        self.assertIsInstance(caught.exception.exceptions[1], ExceptionGroup)

    def test_equal_scenes_are_distinct_instances(self):
        class Equal(Probe):
            def __eq__(self, other):
                return True

        root, modal = Equal(), Equal()
        stack = SceneStack(root)
        stack.push(modal)
        stack.update(InputFrame(), 0)
        self.assertIs(stack.current, modal)
        with self.assertRaises(ValueError):
            stack.push(root)

    def test_nonfinite_delta_rejected(self):
        stack = SceneStack(Probe())
        for delta in (float("nan"), float("inf"), -1):
            with self.assertRaises(ValueError):
                stack.update(InputFrame(), delta)


class TransitionFailureTests(unittest.TestCase):
    def test_replace_failure_does_not_exit_retired_scene_twice(self):
        class Broken(Probe):
            def exit(self):
                super().exit()
                raise ValueError("exit failed")

        old, replacement = Broken(), Probe()
        stack = SceneStack(old)
        stack.replace(replacement)
        with self.assertRaises(ValueError):
            stack.update(InputFrame(), 0)
        stack.close()
        self.assertEqual(old.events.count("exit"), 1)
        self.assertEqual(replacement.events, [])


class InterruptedLifecycleTests(unittest.TestCase):
    def test_close_preserves_interrupts_and_attempts_all_cleanup_once(self):
        for interruption in (KeyboardInterrupt("interrupt"), SystemExit(7)):
            with self.subTest(interruption=type(interruption).__name__):
                order = []
                failure = OSError("root cleanup")

                class Root(Probe):
                    def exit(self):
                        order.append("root")
                        raise failure

                class Modal(Probe):
                    def exit(self):
                        order.append("modal")
                        raise interruption

                stack = SceneStack(Root())
                stack.push(Modal())
                stack.update(InputFrame(), 0)
                with self.assertRaises(BaseExceptionGroup) as caught:
                    stack.close()
                self.assertEqual(caught.exception.exceptions, (interruption, failure))
                self.assertEqual(order, ["modal", "root"])
                stack.close()
                self.assertEqual(order, ["modal", "root"])
                with self.assertRaisesRegex(RuntimeError, "closed"):
                    stack.push(Probe())

    def test_interrupted_initialization_cleans_up_and_preserves_original(self):
        for interruption in (KeyboardInterrupt("interrupt"), SystemExit(7)):
            with self.subTest(interruption=type(interruption).__name__):

                class Interrupted(Probe):
                    def enter(self, stack):
                        super().enter(stack)
                        raise interruption

                scene = Interrupted()
                with self.assertRaises(type(interruption)) as caught:
                    SceneStack(scene)
                self.assertIs(caught.exception, interruption)
                self.assertEqual(scene.events, ["enter", "exit"])

    def test_initialization_error_and_cleanup_interrupt_are_both_preserved(self):
        failure = ValueError("initialization")
        interruption = KeyboardInterrupt("cleanup")

        class Interrupted(Probe):
            def enter(self, stack):
                super().enter(stack)
                raise failure

            def exit(self):
                super().exit()
                raise interruption

        scene = Interrupted()
        with self.assertRaises(BaseExceptionGroup) as caught:
            SceneStack(scene)
        self.assertIs(caught.exception.exceptions[0], failure)
        cleanup = caught.exception.exceptions[1]
        self.assertEqual(cleanup.exceptions, (interruption,))
        self.assertEqual(scene.events, ["enter", "exit"])
