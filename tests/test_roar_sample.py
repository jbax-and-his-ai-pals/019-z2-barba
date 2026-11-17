import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import roar_sample


class RoarSampleTests(unittest.TestCase):
    def test_dmc_encoding_tracks_pcm_and_fits_hardware_length(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = [math.sin(i*2*math.pi*200/44100)*.5 for i in range(11025)]
            roar_sample.pcm_wav(root/'input.wav', source, 44100)
            encoded, info = roar_sample.convert(root/'input.wav', root/'out')
            self.assertEqual(len(encoded) % 16, 1)
            self.assertLessEqual(len(encoded), roar_sample.SAMPLE_CAPACITY)
            self.assertEqual(info['rate_index'], 15)
            self.assertLess(abs(info['duration_seconds']-.25), .01)
            level, decoded = 64, []
            for byte in encoded:
                for bit in range(8):
                    level = min(126, level+2) if byte & (1 << bit) else max(0, level-2)
                    decoded.append(level-64)
            # Compare an interior section, away from fades and length padding.
            rate = info['rate_hz']
            error = sum((decoded[i]-roar_sample.DAC_AMPLITUDE*math.sin(i*2*math.pi*200/rate))**2
                        for i in range(500, 5000))/4500
            self.assertLess(error, 10)
            self.assertLessEqual(abs(decoded[-1]), 2)
            code, update, jaw = roar_sample.title_code(encoded, info)
            self.assertEqual(len(code), 0x4A)
            self.assertEqual(code[update-0xA59E:update-0xA59E+3], bytes.fromhex('ad f0 05'))
            self.assertGreater(jaw, update)

    def test_long_sample_selects_lower_rate_without_changing_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roar_sample.pcm_wav(root/'input.wav', [.3, -.3]*22050, 44100)
            encoded, info = roar_sample.convert(root/'input.wav', root/'out')
            self.assertLess(info['rate_index'], 15)
            self.assertLessEqual(len(encoded), roar_sample.SAMPLE_CAPACITY)
            self.assertLess(abs(info['duration_seconds']-1), .02)


if __name__ == '__main__':
    unittest.main()
