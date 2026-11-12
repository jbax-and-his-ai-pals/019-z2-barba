"""BPS1 source-read/target-read encoder and validating decoder (no dependencies)."""
from __future__ import annotations
import struct
import zlib


def number(value: int) -> bytes:
    result = bytearray()
    while True:
        part = value & 127
        value >>= 7
        if not value:
            result.append(part | 128)
            return bytes(result)
        result.append(part)
        value -= 1


def encode(source: bytes, target: bytes, metadata: str = '',
           source_copies: list[tuple[int, int, int]] | None = None) -> bytes:
    """Encode changes, optionally referring to relocated original bytes.

    Each copy is (target offset, source offset, length). Referencing relocated
    assets avoids putting their original bytes into the distributable patch.
    """
    meta = metadata.encode('utf-8')
    patch = bytearray(b'BPS1' + number(len(source)) + number(len(target)) + number(len(meta)) + meta)
    copies = {}
    previous_end = 0
    for dest, origin, length in sorted(source_copies or []):
        if (dest < previous_end or origin < 0 or length <= 0
                or dest+length > len(target) or origin+length > len(source)
                or target[dest:dest+length] != source[origin:origin+length]):
            raise ValueError('Invalid source-copy region')
        copies[dest] = (origin, length)
        previous_end = dest+length
    i = 0
    source_relative = 0
    while i < len(target):
        if i in copies:
            origin, length = copies[i]
            delta = origin-source_relative
            patch.extend(number(((length-1) << 2) | 2))
            patch.extend(number((abs(delta) << 1) | int(delta < 0)))
            source_relative = origin+length
            i += length
            continue
        same = i < len(source) and target[i] == source[i]
        start = i
        while i < len(target) and i not in copies and (i < len(source) and target[i] == source[i]) == same:
            i += 1
        patch.extend(number(((i-start-1) << 2) | (0 if same else 1)))
        if not same:
            patch.extend(target[start:i])
    patch.extend(struct.pack('<II', zlib.crc32(source), zlib.crc32(target)))
    patch.extend(struct.pack('<I', zlib.crc32(patch)))
    return bytes(patch)


def apply(source: bytes, patch: bytes) -> bytes:
    if len(patch) < 16 or patch[:4] != b'BPS1':
        raise ValueError('Not a BPS1 patch')
    source_crc, target_crc, patch_crc = struct.unpack('<III', patch[-12:])
    if zlib.crc32(patch[:-4]) != patch_crc or zlib.crc32(source) != source_crc:
        raise ValueError('Patch or source checksum mismatch')
    pos = 4
    end = len(patch)-12
    def read_number() -> int:
        nonlocal pos
        result, shift = 0, 1
        while True:
            if pos >= end:
                raise ValueError('Truncated BPS integer')
            value = patch[pos]
            pos += 1
            result += (value & 127) * shift
            if value & 128:
                return result
            shift <<= 7
            result += shift
    size, target_size, meta_size = read_number(), read_number(), read_number()
    if size != len(source):
        raise ValueError('Incorrect source size')
    pos += meta_size
    if pos > end:
        raise ValueError('Truncated metadata')
    target = bytearray()
    source_relative = target_relative = 0
    while len(target) < target_size:
        action = read_number()
        length, mode = (action >> 2)+1, action & 3
        if len(target)+length > target_size:
            raise ValueError('Target size overflow')
        if mode == 0:
            chunk = source[len(target):len(target)+length]
            if len(chunk) != length:
                raise ValueError('Source read out of bounds')
            target.extend(chunk)
        elif mode == 1:
            if pos+length > end:
                raise ValueError('Truncated literal')
            target.extend(patch[pos:pos+length])
            pos += length
        else:
            offset = read_number()
            delta = -(offset >> 1) if offset & 1 else offset >> 1
            if mode == 2:
                source_relative += delta
                if source_relative < 0 or source_relative+length > len(source):
                    raise ValueError('Source copy out of bounds')
                target.extend(source[source_relative:source_relative+length])
                source_relative += length
            else:
                target_relative += delta
                for _ in range(length):
                    if not 0 <= target_relative < len(target):
                        raise ValueError('Target copy out of bounds')
                    target.append(target[target_relative])
                    target_relative += 1
    if pos != end or zlib.crc32(target) != target_crc:
        raise ValueError('Target checksum or action stream mismatch')
    return bytes(target)
