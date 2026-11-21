"""Build Link's octave-up laughs from native DPCM; no sampled assets tracked."""
from __future__ import annotations

import hashlib
import math

from nes import prg_offset
from roar_sample import ORIGINAL_SHA256, SAMPLE_ADDRESS, SAMPLE_CAPACITY, CPU_HZ, PERIODS

LAUGH_ENTRIES = (2, 4, 5, 6, 7)
SHARED_LAUGH_RATES = (6, 6, 6, 10, 10)
SHARED_LAUGH_INDICES = (0, 0, 1, 2, 3)
SHARED_LAUGH_LENGTHS = (65, 49, 49, 49, 49)
COMPACT_LAUGH_GAINS = (4.0, 4.0, 4.0, 2.0)


def compact_laughs(source: bytes, roar_bytes: int) -> list[tuple[int, bytes, bytes]]:
    """Four native voices; the similar opening pair shares a shortened prefix.

    The first byte is silent dither shared with the roar's final byte. The
    caller checks this byte and writes only beyond the roar, never over it.
    """
    address = (SAMPLE_ADDRESS + roar_bytes - 1 + 63) // 64 * 64
    patches = []
    compile_laughs(source)  # Validate the original data and all five pointers.
    for number, (entry, rate) in enumerate(zip((2, 5, 6, 7), (6, 6, 10, 10))):
        table = prg_offset(6, 0x917B + entry*2)
        start = prg_offset(7, 0xC000 + source[table]*64)
        original = source[start:start+source[table+1]*16+1]
        laugh = encode_compact(original, rate, lead_dither=number < 2,
                               boost=COMPACT_LAUGH_GAINS[number])
        if address + len(laugh) > SAMPLE_ADDRESS + SAMPLE_CAPACITY:
            raise ValueError('Roar leaves insufficient space for the compact Game Over laughs')
        start = prg_offset(7, address)
        patches.append((address, laugh, source[start:start+len(laugh)]))
        # Hardware lengths are 16*n+1: adjacent samples can share the last
        # silent byte, recovering an entire 64-byte starting slot here.
        address = (address + len(laugh) - 1 + 63) // 64 * 64
    return patches


def encode_compact(data: bytes, rate: int, *, lead_dither: bool = False,
                   boost: float = 1.0) -> bytes:
    """One conversion from native PCM to twice-speed, boosted DPCM.

    Re-encoding the already re-encoded octave-up sample twice quantizes the
    waveform. At low DMC rates a full-volume target also exceeds the DAC's
    two-step slew limit, rounding the laugh into a nearly featureless triangle.
    Start with a slew-scaled target, then boost it for audible Game Over laughs.
    The hardware's slew limit bounds the actual boost and adds some distortion.
    """
    pcm = decode(data)
    ratio = 2*PERIODS[rate]/PERIODS[15]
    targets = []
    for i in range(math.ceil(len(pcm)/ratio)):
        a, b = int(i*ratio), min(len(pcm), int((i+1)*ratio))
        targets.append(sum(pcm[a:b])/(b-a))
    if boost > 1:
        # Remove treble that spends scarce DAC steps without contributing much
        # audible body. Forward/backward filtering avoids shifting the pitch
        # or the waveform's timing; the louder target then uses those steps.
        targets = low_pass(targets, CPU_HZ/PERIODS[rate], 1000)
    mean = sum(targets)/len(targets)
    # Fit typical slew rather than a single transient: fitting the worst step
    # would make the opening laugh almost inaudible. Faster voices need less
    # attenuation. Boost after normalization; the already stronger final voice
    # uses less gain. The DPCM encoder enforces the hardware slew limit.
    slew = math.sqrt(sum((b-a)**2 for a, b in zip(targets, targets[1:]))
                     / max(1, len(targets)-1))
    gain = min(1.0, 3.0/max(3.0, slew))*boost
    targets = [64+(v-mean)*gain for v in targets]
    if lead_dither:
        targets = [66,64]*4 + targets  # Encodes exactly $55, matching the roar.
    size = (math.ceil(len(targets)/8)+14)//16*16+1
    encoded, level = bytearray(size), 64
    for bit in range(size*8):
        target = targets[bit] if bit < len(targets) else 64
        if target >= level:
            encoded[bit//8] |= 1 << (bit%8)
            level = min(126, level+2)
        else:
            level = max(0, level-2)
    return bytes(encoded)


def resample(data: bytes, source_rate: float, target_rate: float) -> bytes:
    """Re-encode at a lower DMC rate without changing source pitch or duration."""
    pcm = decode(data)
    count = math.ceil(len(pcm)*target_rate/source_rate)
    size = (math.ceil(count/8)+14)//16*16+1
    encoded, level = bytearray(size), 64
    for bit in range(size*8):
        a = int(bit*source_rate/target_rate)
        b = min(len(pcm), max(a+1, int((bit+1)*source_rate/target_rate)))
        target = sum(pcm[a:b])/(b-a) if a < len(pcm) else 64
        if target >= level:
            encoded[bit//8] |= 1 << (bit%8)
            level = min(127, level+2)
        else:
            level = max(0, level-2)
    return bytes(encoded)

def decode(data: bytes, level: int = 64) -> list[int]:
    result = []
    for byte in data:
        for bit in range(8):
            level = min(127, level + 2) if byte & (1 << bit) else max(0, level - 2)
            result.append(level)
    return result


def low_pass(targets: list[float], sample_rate: float, cutoff: float) -> list[float]:
    """Filter in both directions to soften harmonics without shifting timing."""
    alpha = 1-math.exp(-2*math.pi*cutoff/sample_rate)
    for direction in (1, -1):
        level, filtered = 64, []
        for value in targets[::direction]:
            level += alpha*(value-level)
            filtered.append(level)
        targets = filtered[::direction]
    return targets


def octave_up(data: bytes, *, soften: bool = False) -> bytes:
    pcm = decode(data)
    # Two source samples per output sample: exactly twice the pitch. Average
    # pairs to reduce aliasing, retaining the native DAC excursion/volume.
    targets = [(a+b)/2 for a, b in zip(pcm[::2], pcm[1::2])]
    if soften:
        # The two closing laughs have a prominent high overtone. Soften it
        # before encoding and compensate for the filter's loss around 400 Hz.
        targets = low_pass(targets, CPU_HZ/PERIODS[15], 750)
        targets = [64+1.3*(value-64) for value in targets]
    size = ((len(targets)+7)//8 + 14)//16*16 + 1  # hardware: 16*n+1 bytes
    result, level = bytearray(size), 64
    for bit in range(size*8):
        # Settle to the midpoint after the shortened laugh, then silent dither.
        target = targets[bit] if bit < len(targets) else 64
        up = target >= level
        if up:
            result[bit//8] |= 1 << (bit%8)
        level = min(127, level+2) if up else max(0, level-2)
    return bytes(result)


def compile_laughs(source: bytes) -> list[tuple[int, bytes, bytes]]:
    offset = prg_offset(7, SAMPLE_ADDRESS)
    if hashlib.sha256(source[offset:offset+SAMPLE_CAPACITY]).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Original laugh sample allocation differs')
    patches = []
    # Initial E9=2 selects entry 2; the subsequent counter visits 4..7.
    # All sequencing/timer code stays native (23 frames between starts).
    for entry in LAUGH_ENTRIES:
        table = prg_offset(6, 0x917B + entry*2)
        expected = {2: 'cf1c', 4: 'dc14', 5: 'e118', 6: 'e70f', 7: 'ea0f'}[entry]
        if source[table:table+2] != bytes.fromhex(expected):
            raise ValueError('Original laugh pointer/length differs')
        address = 0xC000 + source[table]*64
        count = source[table+1]*16 + 1
        start = prg_offset(7, address)
        original = source[start:start+count]
        if entry == 2 and hashlib.sha256(original).hexdigest() != '1c7d460ccf0e00ff4d341c7bb859000f2109f2648b2e2e4e70a99674ed9c2c71':
            raise ValueError('Original first laugh differs')
        raised = octave_up(original, soften=entry in (6, 7))
        # The first laugh starts on hurt's final byte at F3C0. Move its
        # shortened result to F400, within its own native sample footprint,
        # preserving the entire hurt sample and the experimental allocation.
        if entry == 2:
            address = 0xF400
        start = prg_offset(7, address)
        patches.append((address, raised, source[start:start+len(raised)]))
    return patches


def write_previews(source: bytes, output) -> None:
    """Local A/B references at native spacing; decoded DAC, before NES mixing."""
    from roar_sample import pcm_wav
    output.mkdir(parents=True, exist_ok=True)
    raised = compile_laughs(source)
    native = []
    for entry in LAUGH_ENTRIES:
        table = prg_offset(6, 0x917B+entry*2)
        start = prg_offset(7, 0xC000+source[table]*64)
        native.append(source[start:start+source[table+1]*16+1])
    versions = (
        ('original-game-over-laughs.wav', native, [CPU_HZ/54]*5),
        ('game-over-octave-reference.wav', native, [CPU_HZ/27]*5),
        ('game-over-laugh-preview.wav', [data for _, data, _ in raised], [CPU_HZ/54]*5),
    )
    for name, samples, rates in versions:
        hz, level = 44100, 64
        values = [0.0]*round((4*23/60.099+.3)*hz)
        for number, (sample, rate) in enumerate(zip(samples, rates)):
            pcm = decode(sample, level)
            level = pcm[-1]
            start = round(number*23/60.099*hz)
            for i in range(round(len(pcm)*hz/rate)):
                values[start+i] = (pcm[min(len(pcm)-1, int(i*rate/hz))]-64)/64
        pcm_wav(output/name, values, hz)


if __name__ == '__main__':
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    write_previews((root/'roms/z2.nes').read_bytes(), root/'build')
