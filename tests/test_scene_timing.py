"""Scene lifecycle controls animation time without global timers."""

import unittest

from loom.app import Scene, SceneStack
from loom.input import InputFrame
from loom.timing import Timeline


class AnimatedScene(Scene):
    def enter(self, scenes):
        super().enter(scenes)
        self.timeline = Timeline()
        self.position = self.timeline.tween(0, 100, 1)
        self.notifications = []
        self.timer = self.timeline.call_later(
            1, lambda: self.notifications.append("done")
        )
        self.cover = False

    def update(self, frame, dt):
        self.timeline.update(dt)
        if self.cover:
            self.cover = False
            self.scenes.push(Overlay())

    def exit(self):
        self.timeline.clear()


class Overlay(Scene):
    def update(self, frame, dt):
        if "cancel" in frame.pressed:
            self.scenes.pop()


class SceneTimingTests(unittest.TestCase):
    def test_overlay_pauses_time_and_pop_resumes_without_catchup(self):
        scene = AnimatedScene()
        stack = SceneStack(scene)
        scene.cover = True
        stack.update(InputFrame(), 0.25)
        self.assertEqual(scene.position.value, 25)
        stack.update(InputFrame(), 10)
        self.assertEqual(scene.position.value, 25)
        self.assertEqual(scene.notifications, [])
        stack.update(InputFrame(pressed=frozenset({"cancel"})), 10)
        stack.update(InputFrame(), 0.25)
        self.assertEqual(scene.position.value, 50)
        stack.update(InputFrame(), 0.5)
        self.assertEqual(scene.position.value, 100)
        self.assertEqual(scene.notifications, ["done"])
        stack.close()

    def test_exit_cancels_pending_scene_work(self):
        scene = AnimatedScene()
        stack = SceneStack(scene)
        stack.update(InputFrame(), 0.25)
        stack.close()
        self.assertTrue(scene.position.cancelled)
        self.assertTrue(scene.timer.cancelled)
        scene.timeline.update(100)
        self.assertEqual(scene.position.value, 25)
        self.assertEqual(scene.notifications, [])

    def test_boundary_uses_float_time_without_premature_completion(self):
        from math import nextafter

        timeline = Timeline()
        calls = []
        timer = timeline.call_later(1, lambda: calls.append("done"))
        tween = timeline.tween(0, 10, 1)
        before = nextafter(1.0, 0.0)
        timeline.update(before)
        self.assertFalse(timer.done)
        self.assertFalse(tween.done)
        timeline.update(1.0 - before)
        self.assertTrue(timer.done)
        self.assertEqual(tween.value, 10)
        self.assertEqual(calls, ["done"])
        timeline.update(100)
        self.assertEqual(calls, ["done"])
