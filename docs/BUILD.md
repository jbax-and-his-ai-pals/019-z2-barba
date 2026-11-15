# Build and validation

Requires Python 3.10+ and the ca65/ld65 programs from [cc65](https://cc65.github.io/).
Portable Windows tools may be placed in `.tools/cc65/bin/`. No Python packages
are required. All paths below are relative to the repository root.

On Windows, `./tools/bootstrap.ps1 -WithEmulator` downloads portable cc65 and
Mesen into the ignored `.tools/` folder and verifies their SHA-256 checksums
before extraction. Omit `-WithEmulator` for just the assembler. The cc65 URL is
an upstream snapshot: if upstream replaces it, the locked checksum intentionally
fails. Install ca65/ld65 manually from the official project, or deliberately
review and update `tools/toolchain.json` for the new snapshot. Tools already on
PATH are supported; neither WSL nor a system-wide installation is required.

On Linux, install the `cc65` package with your distribution's package manager.

Place your source ROM at `roms/z2.nes`. The build requires SHA-256:

```text
ad8c0fbcf092bf84b48e69fd3964eea4ed91bfe62abc352943d537979782680c
```

The build will reject other dumps rather than guessing where to patch them.
The original is opened read-only. Never copy a modified ROM over it.

```powershell
python tools/build.py
python -m unittest discover -s tests -v
```

Outputs:

- `build/barba.nes`: playable development ROM; original mapper, header and size.
- `build/barba.bps`: BPS1 patch with source, target, and patch checksums.
- `build/build-report.json`: source/output hashes, symbols and all changed ranges.
- `build/barba-sprites.png`: generated preview of the original pixel artwork.
- Assembly binaries, linker map, and debug symbols for development.

Relocated original overworld graphics use BPS source-copy references. Their
bytes are read from the user's original ROM when applying the patch, rather
than embedded as newly authored patch literals. No ROM is uploaded by the build.

Research graphics can be rendered with `python tools/inspect_chr.py`.
They stay in `build/` and must not be committed.

## Emulator checks

Put portable [Mesen 2.1.1](https://github.com/SourMesen/Mesen2/releases/tag/2.1.1)
at `.tools/mesen/Mesen.exe`. The headless runner uses a local configuration in
that folder; Lua file access is enabled for checked-in test scripts to write
screenshots and reports into `build/`. Networking remains disabled.

```powershell
python tools/emulator_test.py tests/boot.lua --rom roms/z2.nes
python tools/emulator_test.py tests/gameplay.lua
python tools/emulator_test.py tests/combat.lua
python tools/emulator_test.py tests/palace.lua
python tools/emulator_test.py tests/routines.lua
python tools/emulator_test.py tests/breath_height.lua
```

The runner saves screenshots and logs locally. It does not open a GUI.
Emulator scenario coverage is documented separately from full-playthrough status.
Each run uses a fresh save directory under `build/` and explicitly connects an
NES controller, so unknown-ROM database defaults and existing player saves do
not affect the tests. Run scenarios sequentially: the portable emulator settings
and output directory are shared. Lua errors return failure and produce an
associated `*-error.txt` file. Native emulator logs are retained for diagnosis.

GitHub Actions runs ROM-free tests, assembles the custom code, validates the
art compiler, and checks that no ROMs/saves are tracked. Emulator scenarios
require the user's local ROM and are not run in public CI.

## Adding a cold bank-0 hook

Use the reusable bridge in `src/farcall.inc`:

```asm
; Call site and operand must remain mapped (fixed ROM, or test RAM).
    jsr FarCall0
    .word MyBank0Routine
; Resume here in the ACTUAL caller bank, with target A/X/Y/P.
```

1. Put the routine in BANK0 and end with RTS. Do not deliberately leave another
   bank mapped on return.
2. Add the 5-byte call at an instruction-aligned fixed-bank site or proven free
   space. A standalone returning gateway also needs RTS: **6 bytes**, plus the
   original 3-byte hook. Inside an existing gateway: **5 fixed bytes** per call,
   no per-target table entry.
3. Use only guarded overlay.prg/put writes with expected source bytes, covering
   complete original instructions. See FIXED-BANK-AUDIT.md. FF4B and E02C are
   live JMP operands, not padding.
4. Preserve the identity byte at CPU $8506 in every bank. Build guards check
   source and output identities. $0769 is the saved AREA bank, not a current-bank
   shadow; FFC9 is not a general restoration API. The native mapper is unchanged.
5. Run build, unit tests, farcall.lua, affected gameplay scenarios and perf_volley
   sequentially. Never convert EnemyFireGateway fast path or TerrainBatch to this
   slower generic ABI.

Common cost: **20 fixed bytes + 157 bank-0 bytes**, paid once. Incoming A/X/Y/P
and $00/$01 reach the target unchanged; target register/flag/scratch outputs
survive restoration. Hardware B/U status bits are not state. Stack-local frames
nest: budget 15 stack bytes at bridge peak (including caller JSR), plus target
stack use; 9 extra bytes remain live during the target versus ordinary JSR. No
persistent RAM is used. Use in existing serialized/NMI game logic; this does
not provide asynchronous interrupt/mapper arbitration.

Measured on real Mesen 6502/MMC1, excluding a 26-cycle target body including RTS,
the 5-byte call costs **474 - 15*b cycles**, with actual entry PRG bank b=0..7:
474 from bank0, 429 from bank3, 369 from bank7. Operand page crossing adds up to
2 cycles; target low byte $00 adds 6 for RTS-address borrow. Reserve **482 cycles**
worst case under this link layout, plus target work. Recheck branch/table page
costs after relinking. This ABI is for cold hooks, not per-enemy/projectile/terrain.

Current fixed padding free: **16 bytes**, formerly 11 (LAVA 5, GATEWAY 8,
TERRAIN 3). Bank0: 1169 free; bank3: 283. Only the original three proven spans
are used. Rollback: revert this branch commit and rebuild; no source ROM changes.

The emulator runner copies executable dependencies to build/mesen and writes
settings there, never into the shared .tools junction. Run scenarios sequentially.
No ROM, emulator binary, generated state or build output is tracked.
