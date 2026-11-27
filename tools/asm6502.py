"""Minimal 6502 assembler shared by subgame packers and portal helpers."""
from __future__ import annotations


class Asm6502:
    """Minimal 6502 assembler with labels and relative/absolute fixups."""

    def __init__(self, base: int) -> None:
        self.base = base
        self.buf = bytearray()
        self.labels: dict[str, int] = {}
        self.fixups: list[tuple[str, int, str]] = []

    def emit(self, *bs: int) -> None:
        self.buf.extend(bs)

    def label(self, name: str) -> None:
        self.labels[name] = self.base + len(self.buf)

    def branch(self, op: int, target: str) -> None:
        self.emit(op, 0)
        self.fixups.append(('rel', len(self.buf) - 1, target))

    def abs_ref(self, op: int, target: str) -> None:
        self.emit(op, 0, 0)
        self.fixups.append(('abs', len(self.buf) - 2, target))

    def lda_lo(self, target: str) -> None:
        self.emit(0xA9, 0)
        self.fixups.append(('lo', len(self.buf) - 1, target))

    def lda_hi(self, target: str) -> None:
        self.emit(0xA9, 0)
        self.fixups.append(('hi', len(self.buf) - 1, target))

    def finish(self) -> bytes:
        for kind, pos, target in self.fixups:
            addr = self.labels[target]
            if kind == 'rel':
                rel = addr - (self.base + pos + 1)
                assert -128 <= rel <= 127, f'Branch out of range to {target}: {rel}'
                self.buf[pos] = rel & 0xFF
            elif kind == 'lo':
                self.buf[pos] = addr & 0xFF
            elif kind == 'hi':
                self.buf[pos] = (addr >> 8) & 0xFF
            else:
                self.buf[pos] = addr & 0xFF
                self.buf[pos + 1] = (addr >> 8) & 0xFF
        return bytes(self.buf)
