"""Convert a local PCM WAV into Barba's one-shot NES DMC voice.

Only the conversion recipe belongs in Git; recordings and encoded samples stay
under roms/ or build/. No third-party Python packages are needed.
"""
from __future__ import annotations

import hashlib
import math
import struct
import wave
from pathlib import Path

CPU_HZ = 1789773
PERIODS = (428, 380, 340, 320, 286, 254, 226, 214,
           190, 160, 142, 128, 106, 85, 72, 54)
SAMPLE_ADDRESS = 0xF400
SAMPLE_CAPACITY = 0x971  # laugh only; preserve hurt's final byte at $F3C0 too
ORIGINAL_SHA256 = '2d3ebbc486171d52f0f9574da8f7b7e4234de70e580727dd726d5eb77991f204'
DAC_AMPLITUDE = 34


def read_wav(path: Path) -> tuple[list[float], int]:
    with wave.open(str(path), 'rb') as wav:
        channels, width, rate, count = (wav.getnchannels(), wav.getsampwidth(),
                                        wav.getframerate(), wav.getnframes())
        if width not in (1, 2, 3, 4) or wav.getcomptype() != 'NONE':
            raise ValueError('Roar reference must be an uncompressed PCM WAV')
        raw = wav.readframes(count)
    values = []
    for pos in range(0, len(raw), width * channels):
        total = 0
        for channel in range(channels):
            sample = raw[pos + channel*width:pos + (channel+1)*width]
            total += sample[0] - 128 if width == 1 else int.from_bytes(sample, 'little', signed=True)
        values.append(total / (channels * (1 << (width*8 - 1))))
    if not values:
        raise ValueError('Empty roar recording')
    return values, rate


def pcm_wav(path: Path, values: list[float], rate: int) -> None:
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes(b''.join(struct.pack('<h', max(-32768, min(32767, round(v*32767))))
                                for v in values))


def convert(path: Path, output: Path) -> tuple[bytes, dict]:
    values, source_rate = read_wav(path)
    # Strip only near-silence at the boundaries; retain the original pitch and
    # duration. Add a short fade to settle the DAC without a hard end click.
    peak = max(abs(v) for v in values)
    if peak < 0.0001:
        raise ValueError('Roar recording is silent')
    threshold = peak * 0.008
    start = next(i for i, v in enumerate(values) if abs(v) > threshold)
    end = len(values) - next(i for i, v in enumerate(reversed(values)) if abs(v) > threshold)
    values = values[max(0, start-source_rate//200):min(len(values), end+source_rate//100)]
    duration = len(values) / source_rate
    candidates = [i for i, period in enumerate(PERIODS)
                  if math.ceil(math.ceil(duration*CPU_HZ/period)/8/16)*16+1 <= SAMPLE_CAPACITY]
    if not candidates:
        raise ValueError('Roar exceeds the prototype sample slot even at the lowest DMC rate')
    rate_index = max(candidates)
    rate = CPU_HZ / PERIODS[rate_index]
    count = math.ceil(duration*rate)
    byte_count = math.ceil(math.ceil(count/8)/16)*16+1
    mean = sum(values)/len(values)
    peak = max(abs(v-mean) for v in values)
    # Raised from 28 to 34 steps for all uses, with headroom on both sides
    # of the DAC midpoint; title pulse music is also ducked during playback.
    level, encoded, decoded = 64, bytearray(byte_count), []
    for bit in range(byte_count*8):
        position = bit*source_rate/rate
        a, b = int(position), min(len(values), max(int(position)+1, int((bit+1)*source_rate/rate)))
        value = sum(values[a:b])/(b-a) if a < len(values) else mean
        fade = min(1.0, bit/max(1, rate*.005), max(0, count-bit)/max(1, rate*.01))
        target = 64 + (value-mean)/peak*DAC_AMPLITUDE*fade
        up = target >= level
        if up:
            encoded[bit//8] |= 1 << (bit%8)
        level = min(126, level+2) if up else max(0, level-2)
        decoded.append((level-64)/64)
    output.mkdir(parents=True, exist_ok=True)
    pcm_wav(output/'roar-reference.wav', values, source_rate)
    pcm_wav(output/'roar-dpcm-preview.wav', decoded, round(rate))
    (output/'roar.dmc').write_bytes(encoded)
    # Reuse a short prefix for hurt; choose a legal DMC end near 0.55 s whose
    # DAC level is near the midpoint, avoiding a large DC step at the cutoff.
    hurt_lengths = [n for n in range(1, byte_count+1, 16) if .50 <= n*8/rate <= .60]
    hurt_bytes = min(hurt_lengths, key=lambda n: abs(decoded[n*8-1])*10 + abs(n*8/rate-.55)) if hurt_lengths else byte_count
    # Match the injury-only hardware rate steps at audio ticks 17/21/25/29.
    # Full roar bytes stay unchanged; only its short injury playback bends.
    hurt_preview, position = [], 0.0
    while int(position) < hurt_bytes*8:
        tick = int(len(hurt_preview)/rate*60.099)
        steps = sum(tick >= boundary for boundary in (17, 21, 25, 29))
        hurt_rate = CPU_HZ / PERIODS[max(0, rate_index-steps)]
        hurt_preview.append(decoded[int(position)])
        position += hurt_rate/rate
    pcm_wav(output/'roar-hurt-preview.wav', hurt_preview, round(rate))
    return bytes(encoded), {
        'reference_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'rate_index': rate_index, 'rate_hz': rate, 'bytes': byte_count,
        'duration_seconds': byte_count*8/rate,
        'timer_frames': math.ceil(byte_count*8/rate*60.099)+3,
        'address': SAMPLE_ADDRESS,
        'dac_amplitude': DAC_AMPLITUDE,
        'hurt_length': (hurt_bytes-1)//16,
        'hurt_prefix_seconds': hurt_bytes*8/rate,
        'hurt_duration_seconds': len(hurt_preview)/rate,
        'hurt_tail_rate_index': max(0, rate_index-4),
    }


def title_code(sample: bytes, info: dict) -> tuple[bytes, int, int]:
    frames = info['timer_frames']
    if frames > 255:
        raise ValueError('Roar exceeds title timer capacity')
    # The title uses a separate music driver. Its channel-enable instruction is
    # patched to preserve DMC while ROAR_TIMER is nonzero; hardware stops at the
    # sample's end. Do not use the gameplay driver's RAM as title music owns it.
    start = (bytes.fromhex('ee fa 05 a9') + bytes([frames])
             + bytes.fromhex('8d f0 05 a9')
             + bytes([info['rate_index']]) + bytes.fromhex('8d 10 40 a9 d0 8d 12 40 a9')
             + bytes([(len(sample)-1)//16])
             + bytes.fromhex('8d 13 40 a9 40 8d 11 40 a9 0f 8d 15 40 a9 1f 8d 15 40 60'))
    update = 0xA59E + len(start)
    code = start + bytes.fromhex('ad f0 05 f0 03 ce f0 05 4c 4f a5')
    jaw = 0xA59E + len(code)
    # Replace title LDA frame / CMP #$40 with this flag-equivalent helper.
    # A live roar holds the fully open pose; other frames retain native timing.
    code += bytes.fromhex('ad f0 05 f0 04 a9 50 d0 02 a5 12 c9 40 60')
    if len(code) > 0x4A:
        raise ValueError('Title sample routine exceeds existing title allocation')
    return code.ljust(0x4A, b'\xea'), update, jaw
