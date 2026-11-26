# Subgame Portal Intake & Procedural Pool Guide

This repo builds two connected things:
1. **Barba Edition**: a Zelda II ROM hack (`NES 2.0 Mapper 176` / FK23C) starring the Palace 6 dragon **Barba** in a Barba/Link swap.
2. **Subgame ROM Hacks**: a series of NES subgames (such as *Where's Waldo?*, *Friday the 13th*, and planned *Duck Hunt*) accessible **both** through audited, non-quest town doors/hooks in Zelda II **and** as standalone NES ROMs.

## Design Premise (Thematic Crossover)
Each subgame propagates the **Barba/Link swap trope** into another classic NES game while **preserving the guest game's core gameplay**:
* **Gameplay stays authentic** to the guest game (e.g., Zapper/pointer shooting in *Duck Hunt*, crowd-search in *Waldo*).
* **Barba & Zelda II elements carry over thematically**: e.g., in *Duck Hunt*, Level 1 brings over Zelda II's forest clearing art (canopy, trunks, grass, and stacked undergrowth bushes for OAM `$20` behind-bush masking) with **Barba** replacing the dog (running out, leaping behind bushes, popping up with catches or roaring/laughing on a miss).
* **Architecture & Upgrade Philosophy**: Subgame ROMs are **not** constrained to their original mappers or minimal hacks. Migrating each ROM to the best architecture for its needs (e.g., upgrading NROM/UNROM/MMC1 guests to **MMC3**) and individually sprucing it up—with scanline IRQs, CHR-bank animations, audio upgrades, and subtle polish throughout, just as we did for Zelda II—is **strongly encouraged as an ingestion step**.
* **Cross-game rewards**: beating a subgame can unlock persistent transformations or accessories in Zelda II (see [`docs/SUBGAME-REWARDS.md`](SUBGAME-REWARDS.md)).

## 1. Current Architecture

* **Host Portal Runtime ([`src/waldo_portal.inc`](../src/waldo_portal.inc)):**
  * `PortalCount`, `PortalTblTown`, `PortalTblRoom`, `PortalTblPage`,
    `PortalTblXlo`, `PortalTblXhi` (up to `MAX_PORTAL_SLOTS = 4`) in
    `BANK2_SMOKE`.
  * `PortalTblWram`, `PortalTbl5FF0`, `PortalTbl5FF1`, `PortalTbl5FF2`,
    `PortalTblR6`, `PortalTblBootLo`, `PortalTblBootHi` in `BANK2_SMOKE`.
  * `BarbaWaldoEnter6` saves `$0000-$07FF` + PPU nametables/palettes to
    **WRAM Bank 1** (`$A1`), then `PortalTramp2` switches to the guest WRAM
    bank, seeds `$7FF0-$7FF7` from Zelda II's RNG (`$051A-$0521` XOR `$12`,
    ensuring `$7FF0 != 0`), switches `$5FF0-$5FF2`, and jumps to the guest's
    `boot_addr`. Each subgame packer's boot RNG hook reads `$7FF0+` (with a
    non-zero fallback for standalone ROMs) after the guest's RAM clear.
  * `BarbaWaldoRestore6` is the single fixed return address exported to every
    subgame packer.
* **Pool & Manifest ([`tools/portal_pool.py`](../tools/portal_pool.py)):**
  * `CANDIDATE_DOORS`: audited Zelda II town exterior doors that never block
    healers, sages, sword knights, or quest-item NPCs.
  * `SUBGAME_POOL`: registered `SubgameSpec` entries (currently `waldo` and `f13`).
  * `build.py` patches `PortalTbl*` from `portal_pool` and emits
    `build/portal-manifest.json`.
* **Rapid-Test Door Pack ([`tools/create_portal_door_pack.py`](../tools/create_portal_door_pack.py)):**
  * Reads `build/portal-manifest.json` and generates Mesen save states
    (`F1..Fk`) right in front of each placed portal door in `build/barba.nes`.

## 2. 4-Stage Intake Pipeline for New ROMs

### Stage 1: Triage (`roms/candidates/<game>.nes`)
Inspect iNES/NES 2.0 header, vectors (`$FFFA-$FFFF`), and mapper writes:
* **Tier 1 (Easy):** NROM, CNROM, or MMC3 with **CHR-ROM**.
* **Tier 2 (Medium):** UNROM or MMC1 with **CHR-ROM**, or guests using `$6000-$7FFF` WRAM.
* **Tier 3 (Defer):** **CHR-RAM** games, exotic mappers (MMC5, VRC, Sunsoft), or tight DMC/mid-frame tricks.

### Stage 2: Round 1 Minimal Adapter
Keep Round 1 minimal (no custom multi-scenario branches or sprite swaps yet):
1. **Mapper virtualization:** if non-MMC3, rewrite `$8000-$FFFF` bankswitch writes to a WRAM trampoline (see `tools/pack_f13.py`).
2. **`PORTAL_BOOT`:** clean init when entered from Barba.
3. **`PORTAL_NMI_HOOK`:** `Start+Select` (after ~60-frame debounce in `$7FFF` of the guest's WRAM bank) jumps to `PORTAL_RETURN` -> restores Barba (`BarbaWaldoRestore6`).
4. **One `PORTAL_WIN_HOOK`:** intercepts the primary win/ending trigger, sets a reward flag in WRAM bank 0, and returns to Barba.

### Stage 3: Rapid-Test Gate
1. Register the candidate in `SUBGAME_POOL` (`tools/portal_pool.py`) and build a combined ROM.
2. Run `python tools/create_portal_door_pack.py --force --prepare-only` to generate `F1..Fk` door checkpoints.
3. Add a Lua scenario + `tests/<game>_in_rom.lua` verifying:
   * Door entry -> guest NMI ticks cleanly
   * `Start+Select` -> clean return to Barba
   * Pre-win save state -> win hook returns cleanly to Barba

### Stage 4: Greenlight & Round 2
Once Round 1 passes automated Lua checks and human F-key flip-through, mark `status='greenlit'` in `SUBGAME_POOL`. Round 2 can later add custom scenarios (like F13), Barba sprite/roar swaps, and custom door hints.

## 3. Future Barba Enterprise Dashboard Architecture (Planned)
When scaling the web dashboard (`web/index.html`) across all subgames:
* **Top-level grouping by game** (one tab/section per subgame + Zelda II main hack).
* **Per-game subtabs**: `Title`, `In-Game Graphics`, `Needs Work`, and `Sign-Off`, with candidate previews, animation toggles, vote/rank controls, and open notes per item.
