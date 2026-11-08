import unittest

from loom.timing import Timeline, ease_out_cubic, linear, smoothstep


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.timeline = Timeline()
        self.calls = []

    def test_linear_progress_completion_and_pause(self):
        tween = self.timeline.tween(
            10, 30, 2, on_complete=lambda: self.calls.append((tween.value, tween.done))
        )
        self.assertEqual(tween.value, 10)
        self.timeline.update(0)
        self.assertEqual(tween.value, 10)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 15)
        self.assertEqual(tween.value, 15)  # No update: no implicit clock progression.
        self.timeline.update(1.5)
        self.assertEqual(self.calls, [(30, True)])
        self.assertFalse(tween.cancelled)
        self.assertEqual(self.timeline.pending_count, 0)
        self.timeline.update(100)
        self.assertEqual(len(self.calls), 1)

    def test_large_dt_snaps_to_exact_end(self):
        tween = self.timeline.tween(1, -3, 0.25, ease=lambda t: 0)
        self.timeline.update(100)
        self.assertEqual(tween.value, -3)
        self.assertTrue(tween.done)

    def test_named_easing(self):
        self.assertEqual(linear(0.5), 0.5)
        self.assertEqual(smoothstep(0.5), 0.5)
        self.assertEqual(ease_out_cubic(0.5), 0.875)
        for ease in (linear, smoothstep, ease_out_cubic):
            self.assertEqual(ease(0), 0)
            self.assertEqual(ease(1), 1)
        tween = self.timeline.tween(0, 8, 1, ease=ease_out_cubic)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 7)

    def test_timer_zero_waits_until_update(self):
        timer = self.timeline.call_later(0, lambda: self.calls.append(timer.done))
        self.assertFalse(timer.done)
        self.assertEqual(self.calls, [])
        self.timeline.update(0)
        self.assertEqual(self.calls, [True])
        self.timeline.update(0)
        self.assertEqual(self.calls, [True])

    def test_timer_exact_boundary(self):
        timer = self.timeline.call_later(1, lambda: self.calls.append("timer"))
        self.timeline.update(0.25)
        self.timeline.update(0.25)
        self.assertFalse(timer.done)
        self.timeline.update(0.5)
        self.assertTrue(timer.done)
        self.assertEqual(self.calls, ["timer"])

    def test_cancel_keeps_value_without_callback(self):
        tween = self.timeline.tween(
            0, 10, 1, on_complete=lambda: self.calls.append("bad")
        )
        timer = self.timeline.call_later(1, lambda: self.calls.append("bad"))
        self.timeline.update(0.5)
        tween.cancel()
        timer.cancel()
        self.assertEqual(self.timeline.pending_count, 0)
        self.timeline.update(100)
        self.assertEqual(tween.value, 5)
        self.assertTrue(
            tween.done and tween.cancelled and timer.done and timer.cancelled
        )
        self.assertEqual(self.calls, [])

    def test_cancel_completed_is_noop(self):
        timer = self.timeline.call_later(0, lambda: None)
        self.timeline.update(0)
        timer.cancel()
        self.assertTrue(timer.done)
        self.assertFalse(timer.cancelled)

    def test_callback_additions_wait_for_next_update(self):
        added = []

        def first():
            added.append(self.timeline.tween(0, 1, 1))
            self.timeline.call_later(0, lambda: self.calls.append("later"))

        self.timeline.call_later(0, first)
        self.timeline.update(20)
        self.assertEqual(added[0].value, 0)
        self.assertEqual(self.calls, [])
        self.timeline.update(0.5)
        self.assertEqual(added[0].value, 0.5)
        self.assertEqual(self.calls, ["later"])

    def test_clear_inside_callback_cancels_remaining_snapshot(self):
        self.timeline.call_later(0, self.timeline.clear)
        timer = self.timeline.call_later(0, lambda: self.calls.append("bad"))
        tween = self.timeline.tween(0, 1, 1)
        self.timeline.update(1)
        self.assertTrue(timer.cancelled and tween.cancelled)
        self.assertEqual(tween.value, 0)
        self.assertEqual(self.calls, [])

    def test_add_after_clear_starts_next_update(self):
        def first():
            self.timeline.clear()
            self.timeline.call_later(0, lambda: self.calls.append("new"))

        self.timeline.call_later(0, first)
        self.timeline.update(10)
        self.assertEqual(self.calls, [])
        self.timeline.update(0)
        self.assertEqual(self.calls, ["new"])

    def test_callback_failure_is_fail_stop_and_reusable(self):
        added = []

        def fail():
            added.append(self.timeline.call_later(0, lambda: self.calls.append("bad")))
            raise LookupError("callback")

        completed = self.timeline.call_later(0, fail)
        pending = self.timeline.call_later(0, lambda: self.calls.append("bad"))
        with self.assertRaisesRegex(LookupError, "callback"):
            self.timeline.update(1)
        self.assertTrue(completed.done)
        self.assertFalse(completed.cancelled)
        self.assertTrue(pending.cancelled and added[0].cancelled)
        self.assertEqual(self.timeline.pending_count, 0)
        self.timeline.call_later(0, lambda: self.calls.append("good"))
        self.timeline.update(0)
        self.assertEqual(self.calls, ["good"])

    def test_easing_failure_cancels_tween_before_value_changes(self):
        def fail(t):
            raise RuntimeError("easing")

        tween = self.timeline.tween(0, 1, 1, ease=fail)
        pending = self.timeline.call_later(1, lambda: None)
        with self.assertRaisesRegex(RuntimeError, "easing"):
            self.timeline.update(0.5)
        self.assertTrue(tween.cancelled and pending.cancelled)
        self.assertEqual(tween.value, 0)

    def test_recursive_update_rejected_and_outer_update_fail_stops(self):
        done = self.timeline.call_later(0, lambda: self.timeline.update(0))
        pending = self.timeline.call_later(0, lambda: self.calls.append("bad"))
        with self.assertRaisesRegex(RuntimeError, "recursive"):
            self.timeline.update(0)
        self.assertTrue(done.done and pending.cancelled)
        self.timeline.update(0)
        self.assertEqual(self.calls, [])

    def test_finite_overshoot_allowed_nonfinite_rejected(self):
        tween = self.timeline.tween(0, 10, 1, ease=lambda t: 1.2)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 12)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 10)
        for invalid in (float("nan"), float("inf"), True, 10**1000):
            tween = self.timeline.tween(0, 1, 1, ease=lambda t, result=invalid: result)
            with self.assertRaises(ValueError):
                self.timeline.update(0.5)
            self.assertTrue(tween.cancelled)

    def test_weighted_endpoints_avoid_subtraction_overflow(self):
        tween = self.timeline.tween(-1e308, 1e308, 1)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 0)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 1e308)
        oversized = self.timeline.tween(-1e308, 1e308, 1, ease=lambda t: 2)
        with self.assertRaises(ValueError):
            self.timeline.update(0.5)
        self.assertTrue(oversized.cancelled)

    def test_bad_dt_does_not_mutate_pending_tasks(self):
        tween = self.timeline.tween(0, 1, 1)
        for bad in (-1, float("inf"), float("nan"), True, "1", 10**1000):
            with self.assertRaises(ValueError):
                self.timeline.update(bad)
        self.assertFalse(tween.done)
        self.assertEqual(tween.value, 0)
        self.assertEqual(self.timeline.pending_count, 1)
        self.timeline.update(1)
        self.assertTrue(tween.done)

    def test_invalid_tasks_are_not_added(self):
        for bad in (float("inf"), float("nan"), True, "1", 10**1000):
            for arg in ("start", "end", "duration"):
                args = dict(start=0, end=1, duration=1)
                args[arg] = bad
                with self.assertRaises(ValueError):
                    self.timeline.tween(**args)
            with self.assertRaises(ValueError):
                self.timeline.call_later(bad, lambda: None)
        for duration in (0, -1):
            with self.assertRaises(ValueError):
                self.timeline.tween(0, 1, duration)
        with self.assertRaises(ValueError):
            self.timeline.call_later(-1, lambda: None)
        with self.assertRaises(TypeError):
            self.timeline.call_later(0, None)
        with self.assertRaises(TypeError):
            self.timeline.tween(0, 1, 1, ease=None)
        with self.assertRaises(TypeError):
            self.timeline.tween(0, 1, 1, on_complete=1)
        self.assertEqual(self.timeline.pending_count, 0)

    def test_easing_can_clear_without_reviving_task(self):
        def clear(t):
            self.timeline.clear()
            return t

        tween = self.timeline.tween(0, 1, 1, ease=clear)
        self.timeline.update(0.5)
        self.assertTrue(tween.cancelled)
        self.assertEqual(tween.value, 0)
        self.assertEqual(self.timeline.pending_count, 0)

    def test_terminal_handles_release_callbacks_and_easing_references(self):
        import gc
        import weakref

        class Payload:
            def callback(self):
                pass

            def ease(self, progress):
                return progress

        for finish in ("cancel", "complete", "clear"):
            for kind in ("timer", "tween"):
                with self.subTest(finish=finish, kind=kind):
                    payload = Payload()
                    reference = weakref.ref(payload)
                    if kind == "timer":
                        handle = self.timeline.call_later(1, payload.callback)
                    else:
                        handle = self.timeline.tween(
                            0, 1, 1, ease=payload.ease, on_complete=payload.callback
                        )
                    del payload
                    self.assertIsNotNone(reference())
                    if finish == "cancel":
                        handle.cancel()
                    elif finish == "complete":
                        self.timeline.update(1)
                    else:
                        self.timeline.clear()
                    gc.collect()
                    self.assertIsNone(reference())
                    self.assertTrue(handle.done)
                    self.timeline.clear()

    def test_zero_dt_does_not_repeat_custom_easing_after_progress(self):
        calls = []
        tween = self.timeline.tween(0, 1, 1, ease=lambda t: calls.append(t) or t)
        self.timeline.update(0.25)
        self.timeline.update(0)
        self.timeline.update(0)
        self.assertEqual(calls, [0.25])
        self.assertEqual(tween.value, 0.25)

    def test_constant_huge_endpoints_stay_finite_during_overshoot(self):
        tween = self.timeline.tween(1e308, 1e308, 1, ease=lambda t: 2)
        self.timeline.update(0.5)
        self.assertEqual(tween.value, 1e308)
        invalid = self.timeline.tween(1e308, 1e308, 1, ease=lambda t: float("inf"))
        with self.assertRaises(ValueError):
            self.timeline.update(0.25)
        self.assertTrue(invalid.cancelled)
