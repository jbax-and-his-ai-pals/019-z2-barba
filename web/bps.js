/* Client-side BPS1 patcher for user-supplied ROMs (zero server uploads). */
(function (global) {
  'use strict';

  const Z2_SOURCE_SHA256 = 'ad8c0fbcf092bf84b48e69fd3964eea4ed91bfe62abc352943d537979782680c';

  const CRC_TABLE = (() => {
    const t = new Uint32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) {
        c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      }
      t[i] = c >>> 0;
    }
    return t;
  })();

  function crc32(bytes, end) {
    const limit = end === undefined ? bytes.length : end;
    let c = 0xFFFFFFFF;
    for (let i = 0; i < limit; i++) {
      c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
    }
    return (c ^ 0xFFFFFFFF) >>> 0;
  }

  function readU32LE(bytes, offset) {
    return (
      bytes[offset] |
      (bytes[offset + 1] << 8) |
      (bytes[offset + 2] << 16) |
      (bytes[offset + 3] << 24)
    ) >>> 0;
  }

  function parseBpsHeader(patch) {
    if (!(patch instanceof Uint8Array)) patch = new Uint8Array(patch);
    if (patch.length < 16 || patch[0] !== 0x42 || patch[1] !== 0x50 || patch[2] !== 0x53 || patch[3] !== 0x31) {
      throw new Error('Not a valid BPS1 patch file.');
    }
    const end = patch.length - 12;
    const sourceCrc = readU32LE(patch, end);
    const targetCrc = readU32LE(patch, end + 4);
    const patchCrc = readU32LE(patch, end + 8);
    if (crc32(patch, patch.length - 4) !== patchCrc) {
      throw new Error('BPS patch checksum mismatch (corrupted patch file).');
    }

    let pos = 4;
    function readNumber() {
      let result = 0;
      let shift = 1;
      while (true) {
        if (pos >= end) throw new Error('Truncated BPS variable-length integer.');
        const val = patch[pos++];
        result += (val & 0x7F) * shift;
        if (val & 0x80) return result;
        shift *= 128;
        result += shift;
      }
    }

    const sourceSize = readNumber();
    const targetSize = readNumber();
    const metaSize = readNumber();
    if (pos + metaSize > end) throw new Error('Truncated BPS metadata.');
    const metadata = metaSize > 0
      ? new TextDecoder().decode(patch.subarray(pos, pos + metaSize))
      : '';
    pos += metaSize;

    return { patch, pos, end, sourceSize, targetSize, metadata, sourceCrc, targetCrc, patchCrc };
  }

  function applyBps(source, patch) {
    if (!(source instanceof Uint8Array)) source = new Uint8Array(source);
    const hdr = parseBpsHeader(patch);
    if (source.length !== hdr.sourceSize) {
      throw new Error(`Source ROM size mismatch: expected ${hdr.sourceSize} bytes, got ${source.length} bytes.`);
    }
    if (crc32(source) !== hdr.sourceCrc) {
      throw new Error(`Source ROM CRC32 mismatch (expected ${hdr.sourceCrc.toString(16).padStart(8, '0')}, got ${crc32(source).toString(16).padStart(8, '0')}).`);
    }

    let pos = hdr.pos;
    const end = hdr.end;
    const p = hdr.patch;
    function readNumber() {
      let result = 0;
      let shift = 1;
      while (true) {
        if (pos >= end) throw new Error('Truncated BPS command stream.');
        const val = p[pos++];
        result += (val & 0x7F) * shift;
        if (val & 0x80) return result;
        shift *= 128;
        result += shift;
      }
    }

    const target = new Uint8Array(hdr.targetSize);
    let outOffset = 0;
    let sourceRelative = 0;
    let targetRelative = 0;

    while (pos < end) {
      const cmd = readNumber();
      const action = cmd & 3;
      const length = (cmd >>> 2) + 1;
      if (outOffset + length > target.length) {
        throw new Error('BPS output exceeds target size.');
      }
      if (action === 0) {
        // SourceRead
        for (let i = 0; i < length; i++) {
          target[outOffset] = outOffset < source.length ? source[outOffset] : 0;
          outOffset++;
        }
      } else if (action === 1) {
        // TargetRead
        if (pos + length > end) throw new Error('Truncated TargetRead data.');
        target.set(p.subarray(pos, pos + length), outOffset);
        pos += length;
        outOffset += length;
      } else if (action === 2) {
        // SourceCopy
        const raw = readNumber();
        const delta = (raw & 1) ? -(raw >>> 1) : (raw >>> 1);
        sourceRelative += delta;
        if (sourceRelative < 0 || sourceRelative + length > source.length) {
          throw new Error('SourceCopy out of bounds.');
        }
        target.set(source.subarray(sourceRelative, sourceRelative + length), outOffset);
        sourceRelative += length;
        outOffset += length;
      } else {
        // TargetCopy
        const raw = readNumber();
        const delta = (raw & 1) ? -(raw >>> 1) : (raw >>> 1);
        targetRelative += delta;
        if (targetRelative < 0 || targetRelative + length > outOffset + length) {
          throw new Error('TargetCopy out of bounds.');
        }
        for (let i = 0; i < length; i++) {
          target[outOffset++] = target[targetRelative++];
        }
      }
    }

    if (outOffset !== target.length) {
      throw new Error(`BPS output incomplete (${outOffset}/${target.length} bytes).`);
    }
    const actualTargetCrc = crc32(target);
    if (actualTargetCrc !== hdr.targetCrc) {
      throw new Error(`Target ROM CRC32 mismatch (expected ${hdr.targetCrc.toString(16).padStart(8, '0')}, got ${actualTargetCrc.toString(16).padStart(8, '0')}).`);
    }

    return {
      target,
      metadata: hdr.metadata,
      sourceSize: hdr.sourceSize,
      targetSize: hdr.targetSize,
      sourceCrc: hdr.sourceCrc,
      targetCrc: actualTargetCrc,
    };
  }

  async function sha256Hex(bytes) {
    if (!global.crypto || !global.crypto.subtle) return null;
    const buf = await global.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('');
  }

  global.BARBA_BPS = {
    Z2_SOURCE_SHA256,
    crc32,
    parseBpsHeader,
    applyBps,
    sha256Hex,
  };
})(window);
