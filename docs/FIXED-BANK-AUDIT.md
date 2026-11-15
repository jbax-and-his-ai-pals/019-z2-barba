# Fixed-bank audit (starting commit 3ce5d3e)

All addresses are CPU addresses in fixed PRG bank 7. Counts include every byte
reserved/written by Barba, even bytes equal to the original. No original game
bytes are reproduced here. Source: src/barba.cfg, src/barba.asm, tools/build.py,
and the guarded-ROM build/build-report.json patch list.

## Owned allocations

| Range before | Bytes | Purpose | After |
| --- | ---: | --- | --- |
| D39A-D3BA | 33 | LavaSurface hazard body | 11-byte gateway in LAVA; body moved to bank0 |
| D3BB-D3C9 | 15 | NativeShieldFire reconstructed entry + bank round trip | 12 bytes, shares NativeReturn0 |
| FEAA-FEBE | 21 | EnemyFireGateway, including no-switch EXTRA_LIVE fast path | unchanged bytes and cycles |
| FEBF-FEC7 | 9 | ShieldFireGateway | unchanged |
| FF4C-FF60 | 21 | TerrainBatch, one switch pair for all four probes | unchanged bytes and cycles |
| FF61-FF6C | 12 | NativeEnemyFire, native enemy handler + flag-preserving return | unchanged, return tail named NativeReturn0 |

After: FarCall0 + FarCall0Return use D39A-D3AD (20 bytes);
LavaSurface uses D3AE-D3B8 (11); NativeShieldFire D3B9-D3C4 (12).
Free: D3C5-D3C9 = 5, FEC8-FECF = 8, FF6D-FF6F = 3: **16 bytes**.
Before: 0 + 8 + 3 = **11 bytes**, not the older approximate AGENTS estimate.
Bank0 grows from 4067 to 4255 bytes (188); 1169 bytes remain.
Bank3 remains 1618 used / 283 free.

## Every guarded bank-7 patch outside allocations

| Range | Bytes | Purpose |
| --- | ---: | --- |
| C454-C456 | 3 | Palette substitution, first native palette |
| C46C-C46E | 3 | Palette substitution, second native palette |
| D4FE-D500 | 3 | BarbaPreEnemy hook (stomp/pickup) |
| D50D-D50F | 3 | BarbaUpdate hook (projectiles/shouts/roar) |
| D52D-D52F | 3 | BarbaDisplay hook |
| D535-D537 | 3 | BarbaBlocks hook |
| E0A4-E0A6 | 3 | LavaSurface hook |
| E48B-E48E | 4 | EnemyFireGateway hook + pad |
| E617-E619 | 3 | ShieldFireGateway hook |
| E6E2-E6E5 | 4 | Allow fireballs against sword-only targets |
| E9A1 | 1 | Downstab height |
| E9B5 | 1 | Downstab width |
| EB25-EB96 | 114 | Dragon animation metasprite recipes |

Non-allocation writes total 148 bytes. Allocation bytes before 111 / after 106;
all owned fixed-bank writes total **259 before / 254 after**. No new bank-7
write ranges were introduced. Source hash and expected-byte/overlap guards apply.

## Padding evidence and rejected candidates

Read-only reference: .tools/z2disassembly/src/prg7.asm (all original PRG7 lives
in this file). A scan of every source .asm finds no references to any of the
three UNUSED labels, only their definitions. These explicitly annotated spans
have no fall-through: D397 is an indirect JMP, FEA9 an RTS, FF49 a JMP.
Their next live objects are D3CA (table), FED0 (routine), FF70 (reset).
Thus the three existing allocations are the proven reusable padding:

- D39A-D3C9 (48 bytes), lines 3131-3142: bank7_UNUSED_D39A.
- FEAA-FECF (38 bytes), lines 8155-8166: bank7_UNUSED_FEAA.
- FF4C-FF6F (36 bytes), lines 8236-8247: bank7_UNUSED_FF4C.

Other all-FF runs are not automatically free:

- FF4B is the HIGH OPERAND of the live JMP at FF49. Never allocate it.
  The build explicitly checks that entire JMP remains intact.
- E02C likewise belongs to the JMP at E02A. E02D-E02F (3 bytes), lines
  5013-5020, is bank7_table20, behind that terminating JMP. No symbolic
  references were found in any .asm. It is a plausible extra padding candidate,
  but without an exhaustive indirect-read proof it remains **unallocated**.
- E2E7-E2EE (8 bytes), lines 5399-5413, is damage-code-7 DATA in
  bank7_Table_for_Enemy_Damage, not padding. **Rejected**.

No additional region was judged safe enough to use. Remaining headroom is small;
this change provides a reusable cold-hook ABI, not space for unlimited features.

## Mapper evidence and preservation

prg7.asm lines 8297-8311: FFC5 loads zero then enters FFCC; FFC9 loads $0769
then falls into FFCC. FFCC serializes A to MMC1, shifts A four times, and
preserves X/Y but not A/flags. It does NOT update $0769. $0769 is an AREA bank,
not the current bank. No software shadow is introduced and FFCC is untouched.

Instead FarCall0 reads $8506 BEFORE switching: each of banks 0..7 has a distinct
byte there. Bank7's physical byte is at C506 in its fixed mapping. The build
checks the eight identities against source AND final output; future patches
cannot silently invalidate detection. This is read-only ROM identity, not newly
claimed space. The caller's bank stays in a stack-local frame, so nested calls
restore bank0 to bank0 and the outer call restores its actual caller bank.

The entry and exit preserve A/X/Y/P (hardware B/U bits excepted); $00/$01 are
saved/restored during dispatch, and target-written scratch remains visible on
return. No persistent RAM is allocated. Existing combat gateways retain their
faster specialized ABI. Sharing the NativeReturn0 tail saves 3 bytes and adds
only a JMP (3 cycles) to NativeShieldFire; TerrainBatch and EnemyFireGateway's
fast path are unchanged.
