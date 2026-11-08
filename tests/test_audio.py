import unittest

from loom.audio import AudioMixer


class Channel:
    def __init__(self, gain=0.125):
        self._gain = gain
        self.playing = False
        self.calls = []
        self.stop_error = False
        self.play_error = False
        self.gain_failures = 0

    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, value):
        self.calls.append(("gain", value))
        self._gain = value
        if self.gain_failures:
            self.gain_failures -= 1
            raise RuntimeError("gain")

    def play(self, sound, sec=0, loop=False):
        self.calls.append(("play", sound, sec, loop))
        self.playing = True
        if self.play_error:
            raise RuntimeError("play")

    def play_pos(self):
        return (0, 1.0) if self.playing else None

    def stop(self):
        self.calls.append(("stop",))
        if self.stop_error:
            raise RuntimeError("stop")
        self.playing = False


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.channels = [Channel(0.125), Channel(0.25), Channel(0.5), Channel(0.75)]
        self.mixer = AudioMixer(self.channels, {"music": [0], "sfx": [1, 2]})

    def test_baseline_master_bus_volume_and_mute(self):
        self.assertEqual([c.calls for c in self.channels], [[], [], [], []])
        self.mixer.master_volume = 0.5
        self.mixer.set_bus_volume("sfx", 0.25)
        self.assertEqual(
            [c.gain for c in self.channels], [0.0625, 0.03125, 0.0625, 0.75]
        )
        voice = self.mixer.play("music", "sound", loop=True)
        self.mixer.set_bus_muted("music", True)
        self.assertTrue(voice.active)
        self.assertEqual(self.channels[0].gain, 0)
        self.mixer.master_muted = True
        self.assertEqual([c.gain for c in self.channels[:3]], [0, 0, 0])
        self.mixer.master_muted = False
        self.assertEqual(self.channels[0].gain, 0)
        self.mixer.set_bus_muted("music", False)
        self.assertEqual(self.channels[0].gain, 0.0625)
        self.assertEqual(self.mixer.bus_volume("sfx"), 0.25)
        self.assertFalse(self.mixer.bus_muted("music"))

    def test_idle_channel_selection_and_full_does_not_steal(self):
        first = self.mixer.play("sfx", 1)
        second = self.mixer.play("sfx", [2, 3], sec=0.5, loop=True)
        calls = [list(c.calls) for c in self.channels]
        self.assertIsNone(self.mixer.play("sfx", 4))
        self.assertEqual([c.calls for c in self.channels], calls)
        self.assertEqual((first.channel, second.channel), (1, 2))
        self.assertTrue(first.active and second.active)
        self.assertEqual(self.channels[2].calls[-1], ("play", [2, 3], 0.5, True))

    def test_stale_voice_cannot_stop_reused_channel(self):
        old = self.mixer.play("music", 1)
        self.channels[0].playing = False
        self.assertFalse(old.active)
        new = self.mixer.play("music", 2)
        old.stop()
        self.assertTrue(new.active)
        self.assertFalse(old.active)
        new.stop()
        self.assertFalse(new.active)
        fresh = self.mixer.play("music", 3)
        new.stop()
        self.assertTrue(fresh.active)

    def test_stop_bus_and_all_are_owned_only(self):
        music = self.mixer.play("music", 1)
        effect = self.mixer.play("sfx", 2)
        self.channels[3].playing = True
        self.mixer.stop("sfx")
        self.assertTrue(music.active)
        self.assertFalse(effect.active)
        self.mixer.stop()
        self.assertFalse(music.active)
        self.assertTrue(self.channels[3].playing)
        self.assertEqual(self.channels[3].calls, [])

    def test_close_restores_gains_and_is_idempotent(self):
        self.mixer.master_volume = 0.2
        voice = self.mixer.play("music", 1)
        self.channels[3].playing = True
        self.mixer.close()
        self.assertTrue(self.mixer.closed)
        self.assertFalse(voice.active)
        self.assertEqual([c.gain for c in self.channels], [0.125, 0.25, 0.5, 0.75])
        calls = [list(c.calls) for c in self.channels]
        self.mixer.close()
        voice.stop()
        self.assertEqual([c.calls for c in self.channels], calls)
        self.assertTrue(self.channels[3].playing)
        with self.assertRaises(RuntimeError):
            self.mixer.play("music", 1)
        with self.assertRaises(RuntimeError):
            self.mixer.master_volume = 0.5
        with self.assertRaises(RuntimeError):
            self.mixer.stop()

    def test_constructor_validation_is_nonmutating(self):
        for buses in (
            {"a": [0, 0]},
            {"a": [0], "b": [0]},
            {"a": []},
            {"a": [-1]},
            {"a": [4]},
            {"a": [True]},
            {"a": [1.0]},
            {"": [0]},
        ):
            with self.subTest(buses=buses), self.assertRaises(ValueError):
                AudioMixer(self.channels, buses)
        with self.assertRaises(TypeError):
            AudioMixer(self.channels, {"a": b"12"})
        with self.assertRaises(ValueError):
            AudioMixer([self.channels[0], self.channels[0]], {"a": [0, 1]})
        self.channels[1].playing = True
        with self.assertRaises(ValueError):
            AudioMixer(self.channels, {"a": [0, 1]})
        self.assertEqual([c.calls for c in self.channels], [[], [], [], []])

    def test_bad_volumes_and_play_arguments_do_not_write(self):
        for bad in (-1, 1.1, float("nan"), float("inf"), True, "1", 10**1000):
            with self.assertRaises(ValueError):
                self.mixer.master_volume = bad
            with self.assertRaises(ValueError):
                self.mixer.set_bus_volume("sfx", bad)
        with self.assertRaises(TypeError):
            self.mixer.master_muted = 1
        with self.assertRaises(TypeError):
            self.mixer.set_bus_muted("sfx", 1)
        for sec in (-1, float("nan"), True):
            with self.assertRaises(ValueError):
                self.mixer.play("sfx", 1, sec=sec)
        with self.assertRaises(TypeError):
            self.mixer.play("sfx", 1, loop=1)
        with self.assertRaises(KeyError):
            self.mixer.play("unknown", 1)
        self.assertEqual([c.calls for c in self.channels], [[], [], [], []])

    def test_play_failure_stops_partial_playback(self):
        channel = self.channels[0]
        channel.play_error = True
        with self.assertRaisesRegex(RuntimeError, "play"):
            self.mixer.play("music", 1)
        self.assertFalse(channel.playing)
        channel.stop_error = True
        with self.assertRaises(ExceptionGroup) as caught:
            self.mixer.play("music", 2)
        self.assertEqual(len(caught.exception.exceptions), 2)

    def test_gain_failure_rolls_back_and_preserves_settings(self):
        self.channels[1].gain_failures = 1
        with self.assertRaises(ExceptionGroup):
            self.mixer.master_volume = 0.5
        self.assertEqual(self.mixer.master_volume, 1)
        self.assertEqual([c.gain for c in self.channels], [0.125, 0.25, 0.5, 0.75])
        self.channels[1].gain_failures = 2
        with self.assertRaises(ExceptionGroup) as caught:
            self.mixer.set_bus_volume("sfx", 0.2)
        self.assertEqual(len(caught.exception.exceptions), 2)
        self.assertEqual(self.mixer.bus_volume("sfx"), 1)

    def test_stop_failure_still_attempts_all_owned_channels(self):
        first = self.mixer.play("sfx", 1)
        second = self.mixer.play("sfx", 2)
        self.channels[1].stop_error = True
        with self.assertRaises(ExceptionGroup):
            self.mixer.stop("sfx")
        self.assertFalse(first.active or second.active)
        self.assertFalse(self.channels[2].playing)

    def test_close_groups_failures_and_attempts_every_restore(self):
        self.mixer.master_volume = 0.5
        self.channels[0].stop_error = True
        self.channels[1].gain_failures = 1
        with self.assertRaises(ExceptionGroup) as caught:
            self.mixer.close()
        self.assertEqual(len(caught.exception.exceptions), 2)
        self.assertEqual(self.channels[2].gain, 0.5)
        self.assertIn(("stop",), self.channels[2].calls)
        self.assertEqual(self.channels[3].calls, [])
        self.assertTrue(self.mixer.closed)
        self.mixer.close()

    def test_owned_object_cannot_alias_unowned_index(self):
        shared = Channel()
        with self.assertRaises(ValueError):
            AudioMixer([shared, shared], {"music": [0]})
        self.assertEqual(shared.calls, [])
        # Unowned duplicates are unrelated to this mixer's reservation.
        owned = Channel()
        mixer = AudioMixer([owned, shared, shared], {"music": [0]})
        mixer.close()
        self.assertEqual(shared.calls, [])
