"""ROM-free check of pitch conversion and hardware length constraints."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from game_over_audio import decode, octave_up, resample, encode_compact


class GameOverAudioTests(unittest.TestCase):
    def test_compact_pitch_and_shared_silent_byte(self):
        # Native-like vowel fundamental with a second harmonic. Test the
        # direct converter at the most constrained rate used by the build.
        source, level = bytearray(449), 64
        for bit in range(len(source)*8):
            phase = 2*math.pi*270*bit/(1789773/54)
            target = 64+8*math.sin(phase)+3*math.sin(2*phase)
            up = target >= level
            if up:
                source[bit//8] |= 1 << (bit%8)
            level += 2 if up else -2
        encoded = encode_compact(source, 6, lead_dither=True)
        self.assertEqual(len(encoded), 65)
        self.assertEqual(encoded[0], 0x55)
        self.assertEqual(encoded[-1], 0x55)
        pcm = decode(encoded)[16:400]
        rate = 1789773/226
        def power(hz):
            return abs(sum((v-64)*complex(math.cos(2*math.pi*hz*i/rate),
                                         math.sin(2*math.pi*hz*i/rate))
                           for i,v in enumerate(pcm)))**2
        self.assertGreater(power(540), power(270)*50)
        self.assertGreater(power(1080), power(810)*3)
        # The louder production setting trades harmonic detail for volume.
        # Verify the actual encoded signal grows, rather than just its target.
        old_power = power(540)
        boosted = encode_compact(source, 6, lead_dither=True, boost=4.0)
        self.assertEqual(len(boosted), len(encoded))
        self.assertEqual(boosted[0], 0x55)
        self.assertEqual(boosted[-1], 0x55)
        pcm = decode(boosted)[16:400]
        self.assertGreater(power(540), old_power*1.1)
        self.assertGreater(power(540), power(270)*50)

    def test_octave_and_volume(self):
        # Encode a sine at one cycle per 128 DMC bits, then measure the
        # converted waveform against the doubled frequency and the old one.
        source, level = bytearray(385), 64
        for bit in range(len(source)*8):
            up = 64+18*math.sin(2*math.pi*bit/128) >= level
            if up:
                source[bit//8] |= 1 << (bit%8)
            level += 2 if up else -2
        raised = octave_up(source)
        self.assertEqual(len(raised), 193)
        pcm = decode(raised)[64:1472]
        def power(period):
            return abs(sum((v-64)*complex(math.cos(2*math.pi*i/period),
                                         math.sin(2*math.pi*i/period))
                           for i, v in enumerate(pcm)))**2
        self.assertGreater(power(64), power(128)*100)
        self.assertLessEqual(max(pcm)-min(pcm), 40)
        self.assertGreaterEqual(max(pcm)-min(pcm), 30)

    def test_legal_lengths_and_silent_tail(self):
        for size in (241, 321, 385):
            encoded = octave_up(bytes([0x55])*size)
            self.assertEqual(len(encoded)%16, 1)
            self.assertLessEqual(len(encoded), size)
            self.assertLessEqual(abs(decode(encoded)[-1]-64), 2)

    def test_lower_rate_keeps_pitch_and_duration(self):
        # A gentle 200-Hz tone is re-encoded, not slowed down. This catches
        # confusing lower sample data rate with lower playback pitch.
        source_rate, target_rate = 33144, 7919
        source, level = bytearray(321), 64
        for bit in range(len(source)*8):
            up = 64+6*math.sin(2*math.pi*200*bit/source_rate) >= level
            if up:
                source[bit//8] |= 1 << (bit%8)
            level += 2 if up else -2
        encoded = resample(source, source_rate, target_rate)
        self.assertEqual(len(encoded)%16, 1)
        self.assertLess(abs(len(encoded)*8/target_rate-len(source)*8/source_rate), .017)
        pcm = decode(encoded)[40:500]
        def power(hz):
            return abs(sum((v-64)*complex(math.cos(2*math.pi*hz*i/target_rate),
                                         math.sin(2*math.pi*hz*i/target_rate))
                           for i,v in enumerate(pcm)))**2
        self.assertGreater(power(200), power(200*target_rate/source_rate)*20)
