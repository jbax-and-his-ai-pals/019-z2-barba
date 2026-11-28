"""7-bit packed $4011 PCM encoder/decoder for Wheel of Barba's title voice clip."""
from __future__ import annotations

import hashlib
import struct
import wave
from pathlib import Path

CLIP2_ADDR = 0xCD48
CLIP2_SAMPLES = 0x2F00  # 12,032 samples (~0.975s at 12,343 Hz)
CLIP2_PACKED_LEN = (CLIP2_SAMPLES // 8) * 7  # 10,528 bytes
ORIG_FORTUNE_SHA256 = '30301cca66bf8d3905328325023daeede10c0d787f170e8d737e9c16c9487a1c'


def encode_7bit(samples: list[int]) -> bytes:
    """Pack 7-bit unsigned PCM samples (0..127) MSB-first into Bank 3 format."""
    if len(samples) % 8 != 0:
        raise ValueError(f'Sample count must be a multiple of 8, got {len(samples)}')
    out = bytearray()
    for i in range(0, len(samples), 8):
        acc = 0
        for v in samples[i : i + 8]:
            acc = (acc << 7) | (v & 0x7F)
        out.extend(acc.to_bytes(7, 'big'))
    return bytes(out)


def decode_7bit(data: bytes, count: int = CLIP2_SAMPLES) -> list[int]:
    """Decode Bank 3 7-bit packed PCM bytes back into 0..127 DAC samples."""
    out: list[int] = []
    for i in range(0, len(data), 7):
        chunk = data[i : i + 7]
        if len(chunk) < 7:
            break
        acc = int.from_bytes(chunk, 'big')
        for shift in range(49, -1, -7):
            out.append((acc >> shift) & 0x7F)
            if len(out) >= count:
                return out
    return out[:count]


def load_wav_7bit(wav_path: Path, count: int = CLIP2_SAMPLES) -> list[int]:
    """Read a mono/stereo PCM WAV and quantize to `count` 7-bit (0..127) samples."""
    with wave.open(str(wav_path), 'rb') as w:
        ch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    scale = float(1 << (sw * 8 - 1))
    floats: list[float] = []
    for i in range(0, len(raw), ch * sw):
        acc = 0.0
        for c in range(ch):
            s = raw[i + c * sw : i + (c + 1) * sw]
            v = (s[0] - 128) if sw == 1 else int.from_bytes(s, 'little', signed=True)
            acc += v / scale
        floats.append(acc / ch)
    if len(floats) < count:
        floats.extend([0.0] * (count - len(floats)))
    else:
        floats = floats[:count]
    return [max(0, min(127, round(64.0 + v * 63.0))) for v in floats]


def build_barba_title_packed(wav_path: Path) -> bytes:
    """Load `wav_path` and return the exact 10,528-byte Bank 3 $CD48 payload."""
    samples = load_wav_7bit(wav_path, CLIP2_SAMPLES)
    packed = encode_7bit(samples)
    assert len(packed) == CLIP2_PACKED_LEN
    return packed
