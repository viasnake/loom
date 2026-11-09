import math
import unittest

from loom import Scene, SceneStack, InputFrame, SpriteClip, SpritePlayer


FRAMES = ((0, 0, 8, 8), (8, 0, 8, 8), (16, 0, 8, 8))


class SpriteTests(unittest.TestCase):
    def test_clip_snapshot_validation_and_shared_independent_players(self):
        rectangles = [list(frame) for frame in FRAMES]
        clip = SpriteClip(rectangles, fps=4)
        rectangles[0][0] = 99
        rectangles.append([24, 0, 8, 8])
        self.assertEqual(clip.frames, FRAMES)
        self.assertEqual(clip.duration, 0.75)
        first, second = SpritePlayer(clip), SpritePlayer(clip)
        first.update(0.25)
        self.assertEqual(first.frame, FRAMES[1])
        self.assertEqual(second.frame, FRAMES[0])
        with self.assertRaises(AttributeError):
            clip.fps = 2
        for frames in (
            [],
            [(0, 0, 0, 8)],
            [(0, 0, 8, -1)],
            [(-1, 0, 8, 8)],
            [(0, -1, 8, 8)],
            [(0, 0, 8)],
            [(False, 0, 8, 8)],
            [(0.0, 0, 8, 8)],
        ):
            with self.assertRaises(ValueError):
                SpriteClip(frames)
        for fps in (0, -1, True, float("inf"), float("nan"), 10**1000, 5e-324):
            with self.assertRaises(ValueError):
                SpriteClip(FRAMES, fps=fps)
        with self.assertRaises(TypeError):
            SpritePlayer(clip, loop=1)
        with self.assertRaises(TypeError):
            SpritePlayer(FRAMES)

    def test_once_final_frame_gets_full_duration_then_holds_and_restarts(self):
        player = SpritePlayer(SpriteClip(FRAMES, fps=4), loop=False)
        self.assertEqual(player.index, 0)
        player.update(0.5)
        self.assertEqual(player.index, 2)
        self.assertFalse(player.finished)
        player.update(0.125)
        self.assertFalse(player.finished)
        player.update(0.125)
        self.assertTrue(player.finished)
        self.assertEqual(player.frame, FRAMES[2])
        player.update(1e308)
        self.assertEqual(player.index, 2)
        player.restart()
        self.assertEqual(player.index, 0)
        self.assertFalse(player.finished)

    def test_loop_exact_boundary_and_multiple_cycles(self):
        player = SpritePlayer(SpriteClip(FRAMES, fps=4))
        player.update(0.25)
        self.assertEqual(player.index, 1)
        player.update(0.25)
        self.assertEqual(player.index, 2)
        player.update(0.25)
        self.assertEqual(player.index, 0)
        player.update(750.25)
        self.assertEqual(player.index, 1)
        self.assertFalse(player.finished)
        player.update(0)
        self.assertEqual(player.index, 1)

    def test_fractional_frame_ticks_and_no_epsilon_boundary_promotion(self):
        player = SpritePlayer(SpriteClip(FRAMES, fps=10), loop=False)
        player.update(math.nextafter(0.1, 0))
        self.assertEqual(player.index, 0)
        player.restart()
        player.update(0.1)
        self.assertEqual(player.index, 1)
        player.update(0.1)
        self.assertEqual(player.index, 2)
        player.update(0.1)
        self.assertTrue(player.finished)

    def test_public_duration_is_one_cycle_and_just_below_is_not(self):
        for count, fps in ((2, 49), (3, 13)):
            clip = SpriteClip(FRAMES[:count], fps=fps)
            loop = SpritePlayer(clip)
            loop.update(clip.duration)
            self.assertEqual(loop.index, 0)
            loop.restart()
            loop.update(math.nextafter(clip.duration, 0))
            self.assertEqual(loop.index, count - 1)
            once = SpritePlayer(clip, loop=False)
            once.update(math.nextafter(clip.duration, 0))
            self.assertFalse(once.finished)
            once.restart()
            once.update(clip.duration)
            self.assertTrue(once.finished)

    def test_partial_cycle_addition_does_not_round_up_to_wrap(self):
        player = SpritePlayer(SpriteClip(FRAMES, fps=4))
        player.update(0.25)
        player.update(math.nextafter(0.5, 0))
        self.assertEqual(player.index, 2)

    def test_partial_phase_multiplication_does_not_decide_wrap(self):
        for fps, phase in ((3, 0.75), (13, 0.5)):
            with self.subTest(fps=fps):
                clip = SpriteClip(FRAMES[:2], fps=fps)
                player = SpritePlayer(clip)
                player.update(phase / fps)
                remaining_time = (2 - phase) / fps
                player.update(math.nextafter(remaining_time, 0))
                self.assertEqual(player.index, 1)
                player.restart()
                player.update(phase / fps)
                player.update(remaining_time)
                self.assertEqual(player.index, 0)
                player.restart()
                player.update(phase / fps)
                player.update(math.nextafter(remaining_time, math.inf))
                self.assertEqual(player.index, 0)

    def test_huge_dt_and_extreme_fps_do_not_overflow_phase(self):
        for fps in (4, 1e308, 1e-300):
            clip = SpriteClip(FRAMES, fps=fps)
            player = SpritePlayer(clip)
            player.update(1e308)
            self.assertIn(player.index, range(3))
            self.assertFalse(player.finished)
            once = SpritePlayer(clip, loop=False)
            once.update(1e308)
            self.assertTrue(once.finished)
        player = SpritePlayer(SpriteClip(FRAMES[:2], fps=4))
        player.update(1e308)  # Whole .5-second cycles.
        self.assertEqual(player.index, 0)

    def test_invalid_updates_leave_live_and_finished_players_intact(self):
        player = SpritePlayer(SpriteClip(FRAMES, fps=4), loop=False)
        for complete in (False, True):
            player.update(0.25 if not complete else 1)
            snapshot = player.frame, player.index, player.finished
            for dt in (-1, True, float("nan"), float("inf"), 10**1000, "1"):
                with self.assertRaises(ValueError):
                    player.update(dt)
                self.assertEqual(
                    (player.frame, player.index, player.finished), snapshot
                )

    def test_one_frame_and_clip_switch_by_replacement(self):
        clip = SpriteClip([FRAMES[0]], fps=2)
        once, loop = SpritePlayer(clip, loop=False), SpritePlayer(clip)
        once.update(0.25)
        self.assertFalse(once.finished)
        once.update(0.25)
        self.assertTrue(once.finished)
        loop.update(100)
        self.assertEqual(loop.index, 0)
        self.assertFalse(loop.finished)
        replacement = SpritePlayer(SpriteClip([FRAMES[2]], fps=4))
        self.assertEqual(replacement.frame, FRAMES[2])
        self.assertTrue(once.finished)

    def test_scene_pause_blocks_playback_without_global_tasks(self):
        class Playing(Scene):
            def __init__(self):
                self.player = SpritePlayer(SpriteClip(FRAMES, fps=4))

            def update(self, frame, dt):
                self.player.update(dt)

        game = Playing()
        stack = SceneStack(game)
        stack.update(InputFrame(), 0.25)
        stack.push(Scene())
        stack.update(InputFrame(), 0)
        stack.update(InputFrame(), 10)
        self.assertEqual(game.player.index, 1)
        stack.pop()
        stack.update(InputFrame(), 0)
        stack.update(InputFrame(), 0.25)
        self.assertEqual(game.player.index, 2)
        stack.close()
