"""Extract and analyze all Zelda II hack strings for the local dev dashboard.

Parses the live ASM include files and tools/build.py so the Z2 String Review
tab in web/local.html always reflects the actual ROM build strings without
duplicating them by hand. No subgame ROM strings are included here.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

import assets  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

NES_PALETTE_HEX = {
    "black": "#000000",
    "white": "#ECEEEC",
    "blue": "#3032EC",
    "red": "#982220",
    "sky": "#787CEC",
}


def _decode_chr_tile(rom: bytes, chr_off: int, bank: int, tile_id: int) -> list[str]:
    """Decode an 8x8 2bpp NES CHR tile into 8 rows of '0'..'3'."""
    off = chr_off + bank * 4096 + tile_id * 16
    rows: list[str] = []
    for y in range(8):
        p0 = rom[off + y]
        p1 = rom[off + 8 + y]
        rows.append(
            "".join(
                str(((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1))
                for x in range(8)
            )
        )
    return rows


def _extract_nes_font_tiles(root: Path) -> dict[str, list[str]]:
    """Extract Zelda II's 8x8 CHR font and box border tiles from roms/z2.nes + TEXT_GLYPHS."""
    rom_path = root / "roms" / "z2.nes"
    if not rom_path.exists():
        return {}
    rom = rom_path.read_bytes()
    chr_off = 16 + 131072  # 16-byte iNES header + 128KB PRG
    if len(rom) < chr_off + 8 * 4096:
        return {}

    tiles: dict[str, list[str]] = {}
    for i in range(10):
        tiles[str(i)] = _decode_chr_tile(rom, chr_off, 7, 0xD0 + i)
    for i in range(26):
        tiles[chr(ord("A") + i)] = _decode_chr_tile(rom, chr_off, 7, 0xDA + i)
    tiles[" "] = _decode_chr_tile(rom, chr_off, 7, 0xF4)
    tiles["."] = _decode_chr_tile(rom, chr_off, 7, 0xCF)
    tiles["/"] = _decode_chr_tile(rom, chr_off, 7, 0xCE)
    tiles["?"] = _decode_chr_tile(rom, chr_off, 7, 0x34)
    tiles["!"] = _decode_chr_tile(rom, chr_off, 7, 0x36)
    tiles[","] = list(assets.TEXT_GLYPHS[0x33])
    tiles["'"] = list(assets.TEXT_GLYPHS[0x35])
    tiles["@"] = _decode_chr_tile(rom, chr_off, 1, 0x0E)
    tiles["border_corner"] = _decode_chr_tile(rom, chr_off, 7, 0xCA)
    tiles["border_horiz"] = _decode_chr_tile(rom, chr_off, 7, 0xCB)
    tiles["border_vert"] = _decode_chr_tile(rom, chr_off, 7, 0xCC)
    return tiles

_MACRO_LINE_RE = re.compile(r'^\s*(?:TownLine|WaldoLine)\s+"([^"]*)"\s*,\s*\$([0-9A-Fa-f]{2})\b')
_LABEL_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s*(?:;.*)?$')


def _decode_z2_bytes(hex_bytes: list[int]) -> str:
    """Decode Z2 uppercase/punctuation tile bytes ($DA..$F3, $CF='.', $F4=' ')."""
    out: list[str] = []
    for b in hex_bytes:
        if 0xDA <= b <= 0xF3:
            out.append(chr(ord("A") + (b - 0xDA)))
        elif b == 0xCF:
            out.append(".")
        elif b == 0xF4:
            out.append(" ")
        elif b == 0xCC:
            continue  # border pipe in MenuHeaderRow26
        else:
            out.append("?")
    return "".join(out)


def _parse_macro_blocks(path: Path) -> dict[str, str]:
    """Parse Label: followed by TownLine/WaldoLine macros into {label: text}."""
    blocks: dict[str, str] = {}
    cur_label: str | None = None
    cur_lines: list[str] = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        m_lbl = _LABEL_RE.match(raw)
        if m_lbl:
            if cur_label and cur_lines:
                blocks[cur_label] = "\n".join(cur_lines)
            cur_label = m_lbl.group(1)
            cur_lines = []
            continue

        m_line = _MACRO_LINE_RE.match(raw)
        if m_line and cur_label is not None:
            cur_lines.append(m_line.group(1))
            if m_line.group(2).upper() == "FF":
                blocks[cur_label] = "\n".join(cur_lines)
                cur_label = None
                cur_lines = []
            continue

        stripped = raw.strip()
        if stripped and not stripped.startswith(";"):
            if cur_label and cur_lines:
                blocks[cur_label] = "\n".join(cur_lines)
            cur_label = None
            cur_lines = []

    if cur_label and cur_lines:
        blocks[cur_label] = "\n".join(cur_lines)
    return blocks


def _parse_byte_table(path: Path, label: str, count: int) -> list[str]:
    """Extract `count` consecutive `.byte` rows after `label:` and decode Z2 tiles."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{label}:"):
            start_idx = i + 1
            break
    if start_idx is None:
        raise ValueError(f"Missing label {label!r} in {path}")

    rows: list[str] = []
    for line in lines[start_idx:]:
        stripped = line.split(";", 1)[0].strip()
        if not stripped:
            continue
        if stripped.startswith(".byte"):
            hex_vals = [int(m, 16) for m in re.findall(r"\$([0-9A-Fa-f]{2})", stripped)]
            rows.append(_decode_z2_bytes(hex_vals))
            if len(rows) == count:
                break
        elif rows:
            break
    if len(rows) != count:
        raise ValueError(f"Expected {count} .byte rows for {label!r} in {path}, got {len(rows)}")
    return rows


def _extract_build_py_strings(build_py: Path) -> dict[str, Any]:
    """Extract string literals from tools/build.py via AST/source parsing."""
    src = build_py.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(build_py))

    in_place_town: list[tuple[int, str, str, str]] = []
    story_lines: list[str] = []
    expected_story: list[str] = []
    ending_wakeup: str = ""
    credit_entries: list[Any] = []

    for node in ast.walk(tree):
        # 1. In-place town dialogue replacements: for address, name, original, dialogue in (...)
        if (
            isinstance(node, ast.For)
            and isinstance(node.target, ast.Tuple)
            and [getattr(e, "id", None) for e in node.target.elts]
            == ["address", "name", "original", "dialogue"]
            and isinstance(node.iter, ast.Tuple)
        ):
            for elt in node.iter.elts:
                val = ast.literal_eval(elt)
                in_place_town.append(val)

        # 2. story_lines = [...]
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id == "story_lines":
                story_lines = ast.literal_eval(node.value)
            elif isinstance(tgt, ast.Name) and tgt.id == "credit_entries":
                credit_entries = ast.literal_eval(node.value)
            elif isinstance(tgt, ast.Name) and tgt.id == "ending_text":
                if isinstance(node.value, ast.Call) and node.value.args:
                    ending_wakeup = ast.literal_eval(node.value.args[0])

        # 3. expected_story = b''.join(encode_story_line(line) for line in [...])
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "expected_story"
        ):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.List):
                    expected_story = ast.literal_eval(sub)
                    break

    if not in_place_town or not story_lines or not ending_wakeup or not credit_entries:
        raise ValueError("Failed to extract all string tables from tools/build.py")

    return {
        "in_place_town": in_place_town,
        "story_lines": story_lines,
        "expected_story": expected_story,
        "ending_wakeup": ending_wakeup,
        "credit_entries": credit_entries,
    }


def _make_entry(
    *,
    sid: str,
    label: str,
    area: str,
    character: str,
    source_file: str,
    location: str,
    text: str,
    max_line_len: int,
    max_lines: int,
    allowed_chars: str,
    allowed_regex: str,
    wrap_mode: str = "newline",
    exact_line_len: bool = False,
    max_bytes: int | None = None,
    includes_terminator_in_bytes: bool = True,
    vanilla_text: str | None = None,
    notes: str = "",
    preview_kind: str = "town_box_outdoor",
) -> dict[str, Any]:
    return {
        "id": sid,
        "label": label,
        "area": area,
        "character": character,
        "source_file": source_file,
        "location": location,
        "text": text,
        "vanilla_text": vanilla_text,
        "preview_kind": preview_kind,
        "constraints": {
            "max_line_len": max_line_len,
            "exact_line_len": exact_line_len,
            "max_lines": max_lines,
            "max_bytes": max_bytes,
            "includes_terminator_in_bytes": includes_terminator_in_bytes,
            "allowed_chars": allowed_chars,
            "allowed_regex": allowed_regex,
            "wrap_mode": wrap_mode,
        },
        "notes": notes,
    }


def build_z2_strings_payload(root: Path = ROOT) -> dict[str, Any]:
    """Build the full Zelda II string review payload for the local dashboard."""
    entries: list[dict[str, Any]] = []

    build_data = _extract_build_py_strings(root / "tools" / "build.py")
    town_blocks = _parse_macro_blocks(root / "src" / "town_dialogue.inc")
    sign_blocks = _parse_macro_blocks(root / "src" / "sign.inc")
    sage_blocks = _parse_macro_blocks(root / "src" / "sage_basement.inc")
    waldo_blocks = _parse_macro_blocks(root / "src" / "waldo_portal.inc")

    town_macro_chars = "A-Z 0-9 space . , / ! ? ' newline"
    town_macro_regex = r"^[A-Z0-9 .,/!?\'\n]+$"
    waldo_macro_chars = "A-Z 0-9 space . , / ! ? ' newline"
    waldo_macro_regex = r"^[A-Z0-9 .,/!?\'\n]+$"
    inplace_chars = "A-Z 0-9 space . , / ! ? ' newline"
    inplace_regex = r"^[A-Z0-9 .,/!?\'\n]+$"

    # 1. Title Screen & Game Over
    entries.append(
        _make_entry(
            sid="title_story_scroll",
            label="Title Screen Story Scroll (13 rows x 28 cols)",
            area="Title & Game Over",
            character="Narrator",
            source_file="tools/build.py",
            location="Bank 5 $A932",
            text="\n".join(build_data["story_lines"]),
            vanilla_text="\n".join(build_data["expected_story"]),
            max_line_len=28,
            exact_line_len=True,
            max_lines=13,
            max_bytes=13 * 29,
            includes_terminator_in_bytes=True,
            allowed_chars="A-Z 0-9 space . , @ (copyright)",
            allowed_regex=r"^[A-Z0-9 .,@\n]+$",
            wrap_mode="fixed_row",
            notes="Each of the 13 rows must be padded with spaces to exact 28 chars.",
            preview_kind="title_story",
        )
    )
    entries.append(
        _make_entry(
            sid="game_over_subtitle",
            label="Game Over Subtitle",
            area="Title & Game Over",
            character="Game Over Screen",
            source_file="tools/build.py",
            location="Bank 0 $8010",
            text="LINK KEEPS LAVA",
            vanilla_text="RETURN OF GANON",
            max_line_len=15,
            exact_line_len=True,
            max_lines=1,
            max_bytes=15,
            includes_terminator_in_bytes=False,
            allowed_chars="A-Z space",
            allowed_regex=r"^[A-Z ]+$",
            wrap_mode="single",
            notes="In-place 15-byte replacement over RETURN OF GANON.",
            preview_kind="game_over_banner",
        )
    )

    # 2. In-place Town Dialogue Replacements (tools/build.py)
    inplace_meta = {
        "Mido downstab": ("Mido", "Downstab Knight", "Mido — Downstab Knight", "town_box_indoor"),
        "Darunia upstab": ("Darunia", "Upstab Knight", "Darunia — Upstab Knight", "town_box_indoor"),
        "Saria mirror lady": ("Saria", "Mirror Lady", "Saria — Mirror Lady", "town_box_outdoor"),
        "Saria bridge guard": ("Saria", "River Guard", "Saria — River Guard", "town_box_indoor"),
        "Bagu note": ("Bagu's Cabin", "Bagu", "Bagu — Note to Guard", "town_box_indoor"),
        "Bagu location": ("Saria", "Bagu's Brother", "Saria — Bagu's Brother", "town_box_outdoor"),
    }
    for addr, name, original, dialogue in build_data["in_place_town"]:
        area, char, label, pkind = inplace_meta.get(name, ("Towns (In-Place)", name, name, "town_box_outdoor"))
        orig_lines = original.splitlines()
        entries.append(
            _make_entry(
                sid=f"inplace_{name.lower().replace(' ', '_')}",
                label=label,
                area=area,
                character=char,
                source_file="tools/build.py",
                location=f"Bank 3 ${addr:04X}",
                text=dialogue,
                vanilla_text=original,
                max_line_len=14,
                max_lines=len(orig_lines),
                max_bytes=len(original) + 1,
                includes_terminator_in_bytes=True,
                allowed_chars=inplace_chars,
                allowed_regex=inplace_regex,
                wrap_mode="newline",
                notes=f"In-place Bank 3 replacement; max {len(original)} chars + $FF ({len(orig_lines)} lines).",
                preview_kind=pkind,
            )
        )

    # 3. Saria Sign (src/sign.inc)
    entries.append(
        _make_entry(
            sid="saria_sign_text",
            label="Saria Town Welcome Sign",
            area="Saria",
            character="Town Sign",
            source_file="src/sign.inc",
            location="BANK3_PAD (SariaSignText)",
            text=sign_blocks["SariaSignText"],
            max_line_len=14,
            max_lines=4,
            max_bytes=64,
            allowed_chars=town_macro_chars,
            allowed_regex=town_macro_regex,
            notes="Custom Saria town entrance sign warning about the foul water.",
        )
    )

    # 4. Rauru Sage Basement Sequence (src/sage_basement.inc)
    sage_items = [
        ("SageWaitText", "Rauru Sage — Box 1 (Callout)"),
        ("SageUmText", "Rauru Sage — Box 2 & 5 (Hesitation)"),
        ("SageThinkText", "Rauru Sage — Box 3 (Question Pt. 1)"),
        ("SageDragonText", "Rauru Sage — Box 4 (Question Pt. 2)"),
        ("SageNevermindText", "Rauru Sage — Box 6 (Dismissal)"),
    ]
    for lbl, nice_label in sage_items:
        entries.append(
            _make_entry(
                sid=f"sage_{lbl.lower()}",
                label=nice_label,
                area="Rauru",
                character="Rauru Sage",
                source_file="src/sage_basement.inc",
                location=f"BANK3_PAD ({lbl})",
                text=sage_blocks[lbl],
                max_line_len=14,
                max_lines=4,
                max_bytes=64,
                allowed_chars=town_macro_chars,
                allowed_regex=town_macro_regex,
                notes="Post-SCALES basement sequence; plays automatically as Barba leaves.",
                preview_kind="town_box_indoor",
            )
        )

    # 5. Town Villager Panic, Indoor NPCs, Burned Signs & Error Ash (src/town_dialogue.inc)
    town_dlg_meta = [
        ("TownFearText", "Towns (General)", "Panicking Villager", "Villager Panic #1 (Barba's In Town)"),
        ("TownFearHide", "Towns (General)", "Panicking Villager", "Villager Panic #2 (Get Inside)"),
        ("TownFearLeaving", "Towns (General)", "Panicking Villager", "Villager Panic #3 (Getting Out)"),
        ("TownFearPlea", "Towns (General)", "Panicking Villager", "Villager Panic #4 (Taste Terrible)"),
        ("TownFearBarbaAlert", "Towns (General)", "Panicking Villager", "Villager Panic #5 (Lock Doors)"),
        ("TownFearBarbaLoose", "Towns (General)", "Panicking Villager", "Villager Panic #6 (Barba Is Loose)"),
        ("TownFearBarbaSight", "Towns (General)", "Panicking Villager", "Villager Panic #7 (Really Barba?!)"),
        ("TownFearBarbaBurn", "Towns (General)", "Panicking Villager", "Villager Panic #8 (Burn Town Down)"),
        ("TownWiseManText", "Towns (General)", "Wise Man", "Wise Man — Spare My Life"),
        ("TownHealerText", "Towns (General)", "Healer", "Healer — Heal Your Wounds"),
        ("TownMagicText", "Towns (General)", "Magic Man", "Magic Man — Fill Magic Bar"),
        ("SignChar", "Towns (General)", "Burned Sign", "Burned Sign #1 (Completely Charred)"),
        ("SignBurned", "Towns (General)", "Burned Sign", "Burned Sign #2 (Burned to Ash)"),
        ("SignAshPile", "Towns (General)", "Burned Sign", "Burned Sign #3 (Smoking Pile)"),
        ("SignWhatLeft", "Towns (General)", "Burned Sign", "Burned Sign #4 (Whatever Is Left)"),
        ("SignDidThat", "Towns (General)", "Burned Sign", "Burned Sign #5 (You Did That)"),
        ("SignWasSign", "Towns (General)", "Burned Sign", "Burned Sign #6 (Thanks Barba)"),
        ("ErrorAshText", "Ruto", "Error", "Error's Ash Pile"),
    ]
    for lbl, area, char, nice_label in town_dlg_meta:
        pkind = "town_box_indoor" if lbl in ("TownWiseManText", "TownHealerText", "TownMagicText") else "town_box_outdoor"
        entries.append(
            _make_entry(
                sid=f"town_{lbl.lower()}",
                label=nice_label,
                area=area,
                character=char,
                source_file="src/town_dialogue.inc",
                location=f"PORTAL_BANK ({lbl})",
                text=town_blocks[lbl],
                max_line_len=14,
                max_lines=4,
                max_bytes=64,
                allowed_chars=town_macro_chars,
                allowed_regex=town_macro_regex,
                notes="Copied into ARCADE_DLG_BUF ($63C0-$63FF, 64-byte limit).",
                preview_kind=pkind,
            )
        )

    # 6. Rauru Arcade & Crossover Portals (src/waldo_portal.inc)
    arcade_cabinet_meta = [
        ("ArcadeName00", "Cabinet #00 — Where's Barba?"),
        ("ArcadeName01", "Cabinet #01 — Friday 13th"),
        ("ArcadeName02", "Cabinet #02 — Barba's Beef"),
        ("ArcadeName03", "Cabinet #03 — Barba Kong"),
        ("ArcadeName04", "Cabinet #04 — Super Barba"),
        ("ArcadeName05", "Cabinet #05 — Monster Hunt"),
        ("ArcadeName07", "Cabinet #07 — Barba Man 2"),
        ("ArcadeName08", "Cabinet #08 — Wheel of Barba"),
        ("ArcadeName09", "Cabinet #09 — Legend of Barba"),
        ("ArcadeName10", "Cabinet #10 — Barba Punch-Out!!"),
        ("ArcadeNameDefault", "Cabinet Fallback (Unassigned)"),
        ("OutOfOrderText", "Cabinet Out of Order"),
    ]
    for lbl, nice_label in arcade_cabinet_meta:
        entries.append(
            _make_entry(
                sid=f"portal_{lbl.lower()}",
                label=nice_label,
                area="Rauru Arcade & Portals",
                character="Arcade Cabinet",
                source_file="src/waldo_portal.inc",
                location=f"PORTAL_BANK ({lbl})",
                text=waldo_blocks[lbl],
                max_line_len=14,
                max_lines=4,
                max_bytes=64,
                allowed_chars=waldo_macro_chars,
                allowed_regex=waldo_macro_regex,
                notes="Displayed when inspecting an arcade cabinet in Rauru's Arcade.",
                preview_kind="town_box_indoor",
            )
        )

    win_return_meta = [
        ("WinReturnText01", "Clear Reward #01 — Where's Barba?"),
        ("WinReturnText02", "Clear Reward #02 — Friday 13th"),
        ("WinReturnText03", "Clear Reward #03 — Barba's Beef"),
        ("WinReturnText04", "Clear Reward #04 — Barba Kong"),
        ("WinReturnText05", "Clear Reward #05 — Super Barba"),
        ("WinReturnText06", "Clear Reward #06 — Monster Hunt"),
        ("WinReturnText07", "Clear Reward #07 — Barba Man 2"),
        ("WinReturnText08", "Clear Reward #08 — Wheel of Barba"),
        ("WinReturnText09", "Clear Reward #09 — Legend of Barba"),
        ("WinReturnText10", "Clear Reward #10 — Barba Punch-Out!!"),
    ]
    for lbl, nice_label in win_return_meta:
        entries.append(
            _make_entry(
                sid=f"portal_{lbl.lower()}",
                label=nice_label,
                area="Rauru Arcade & Portals",
                character="Portal Reward",
                source_file="src/waldo_portal.inc",
                location=f"PORTAL_BANK ({lbl})",
                text=waldo_blocks[lbl],
                max_line_len=14,
                max_lines=4,
                max_bytes=64,
                allowed_chars=waldo_macro_chars,
                allowed_regex=waldo_macro_regex,
                notes="Town-return dialogue box shown after clearing a subgame.",
            )
        )

    nontown_rows = [
        _parse_byte_table(root / "src" / "waldo_portal.inc", f"NonTownWinL{i}", 1)[0]
        for i in (1, 2, 3)
    ]
    entries.append(
        _make_entry(
            sid="portal_nontown_win",
            label="Non-Town Subgame Clear Banner",
            area="Rauru Arcade & Portals",
            character="Portal Reward",
            source_file="src/waldo_portal.inc",
            location="PORTAL_BANK (NonTownWinL1..3)",
            text="\n".join(nontown_rows),
            max_line_len=14,
            exact_line_len=True,
            max_lines=3,
            max_bytes=42,
            includes_terminator_in_bytes=False,
            allowed_chars="A-Z space",
            allowed_regex=r"^[A-Z \n]+$",
            wrap_mode="fixed_row",
            notes="3 fixed 14-tile rows drawn directly to nametable when returning to non-town rooms.",
            preview_kind="nontown_win_box",
        )
    )

    for i in range(4):
        lbl = f"ArcadeDlg{i}"
        entries.append(
            _make_entry(
                sid=f"portal_{lbl.lower()}",
                label=f"Arcade Patron #{i + 1}",
                area="Rauru Arcade & Portals",
                character="Arcade Patron",
                source_file="src/waldo_portal.inc",
                location=f"PORTAL_BANK ({lbl})",
                text=waldo_blocks[lbl],
                max_line_len=14,
                max_lines=4,
                max_bytes=64,
                allowed_chars=waldo_macro_chars,
                allowed_regex=waldo_macro_regex,
                notes="Dialogue for NPCs hanging out inside the Rauru Arcade.",
                preview_kind="town_box_indoor",
            )
        )

    # 7. Pause / Spell & Gear Menu (src/arcade_spells.inc)
    spells_path = root / "src" / "arcade_spells.inc"
    menu_hdr_rows = _parse_byte_table(spells_path, "MenuHeaderRow26", 2)
    entries.append(
        _make_entry(
            sid="menu_header_cols",
            label="Spell Menu Column Headers (Hyrule / Arcade)",
            area="Pause / Spell & Gear Menu",
            character="Menu UI",
            source_file="src/arcade_spells.inc",
            location="BANK1_SOULS (MenuHeaderRow26)",
            text="\n".join(r.strip() for r in menu_hdr_rows),
            max_line_len=10,
            max_lines=2,
            max_bytes=26,
            includes_terminator_in_bytes=False,
            allowed_chars="A-Z space",
            allowed_regex=r"^[A-Z \n]+$",
            wrap_mode="fixed_row",
            notes="26-tile header row split into left (Hyrule) and right (Arcade) columns.",
            preview_kind="pause_menu_box",
        )
    )

    hyrule_spells = _parse_byte_table(spells_path, "HyruleSpellNames", 8)
    for idx, name in enumerate(hyrule_spells):
        entries.append(
            _make_entry(
                sid=f"spell_hyrule_{idx}",
                label=f"Hyrule Spell #{idx + 1}",
                area="Pause / Spell & Gear Menu",
                character="Hyrule Spells",
                source_file="src/arcade_spells.inc",
                location=f"BANK1_SPELLS (HyruleSpellNames+{idx * 7})",
                text=name,
                max_line_len=7,
                exact_line_len=True,
                max_lines=1,
                max_bytes=7,
                includes_terminator_in_bytes=False,
                allowed_chars="A-Z . (dot leader)",
                allowed_regex=r"^[A-Z.]+$",
                wrap_mode="single",
                notes="Fixed 7-char slot padded with '.' ($CF) dot leaders.",
                preview_kind="pause_menu_box",
            )
        )

    arcade_spells = _parse_byte_table(spells_path, "ArcadeSpellNames", 10)
    for idx, name in enumerate(arcade_spells):
        entries.append(
            _make_entry(
                sid=f"spell_arcade_{idx}",
                label=f"Arcade Spell #{idx + 1}",
                area="Pause / Spell & Gear Menu",
                character="Arcade Spells",
                source_file="src/arcade_spells.inc",
                location=f"BANK1_SPELLS (ArcadeSpellNames+{idx * 6})",
                text=name,
                max_line_len=6,
                exact_line_len=True,
                max_lines=1,
                max_bytes=6,
                includes_terminator_in_bytes=False,
                allowed_chars="A-Z . (dot leader)",
                allowed_regex=r"^[A-Z.]+$",
                wrap_mode="single",
                notes="Fixed 6-char slot padded with '.' ($CF) dot leaders.",
                preview_kind="pause_menu_box",
            )
        )

    gear_names = _parse_byte_table(spells_path, "GearNameTbl", 5)
    for idx, name in enumerate(gear_names):
        entries.append(
            _make_entry(
                sid=f"gear_name_{idx}",
                label=f"Cosmetic Gear #{idx + 1}",
                area="Pause / Spell & Gear Menu",
                character="Cosmetic Gear",
                source_file="src/arcade_spells.inc",
                location=f"BANK1_SOULS (GearNameTbl+{idx * 4})",
                text=name,
                max_line_len=4,
                exact_line_len=True,
                max_lines=1,
                max_bytes=4,
                includes_terminator_in_bytes=False,
                allowed_chars="A-Z space",
                allowed_regex=r"^[A-Z ]+$",
                wrap_mode="single",
                notes="Fixed 4-char slot in the pause menu gear tray.",
                preview_kind="pause_menu_box",
            )
        )

    # 8. Ending & Credits (tools/build.py)
    raw_end = build_data["ending_wakeup"]
    end_lines = [raw_end[i : i + 15] for i in range(0, len(raw_end), 15)]
    entries.append(
        _make_entry(
            sid="ending_zelda_wakeup",
            label="Zelda Wake-Up Dialogue (4 rows x 15 cols)",
            area="Ending & Credits",
            character="Princess Zelda",
            source_file="tools/build.py",
            location="Bank 5 $BDA1",
            text="\n".join(end_lines),
            max_line_len=15,
            exact_line_len=True,
            max_lines=4,
            max_bytes=61,
            includes_terminator_in_bytes=True,
            allowed_chars="A-Z space ! ? .",
            allowed_regex=r"^[A-Z !?.\n]+$",
            wrap_mode="fixed_row",
            notes="Wraps every 15 chars with no $FD byte; pad each line to 15 chars with spaces.",
            preview_kind="ending_wakeup",
        )
    )

    credit_idx = 0
    for entry in build_data["credit_entries"]:
        if entry == "__PROG__":
            continue
        credit_idx += 1
        rows = [text for _hi, _lo, text in entry]
        joined = "\n".join(rows)
        is_custom = any(
            k in joined for k in ("BARBA", "JERBTRUNDLES", "LAVA RECLAIMED", "PUSH START")
        )
        entries.append(
            _make_entry(
                sid=f"ending_credit_{credit_idx:02d}",
                label=f"Credits Slide #{credit_idx}" + (" (Barba Edition)" if is_custom else ""),
                area="Ending & Credits",
                character="Credits (Custom)" if is_custom else "Credits (Vanilla)",
                source_file="tools/build.py",
                location="Bank 5 $9259 (credit_entries)",
                text=joined,
                max_line_len=20,
                max_lines=len(rows),
                max_bytes=None,
                includes_terminator_in_bytes=True,
                allowed_chars="A-Z space .",
                allowed_regex=r"^[A-Z .\n]+$",
                wrap_mode="fixed_row",
                notes="All credit packets combined must fit in Bank 5 $9259-$93FF (423 bytes).",
                preview_kind="ending_credits",
            )
        )

    areas = list(dict.fromkeys(e["area"] for e in entries))
    characters = list(dict.fromkeys(e["character"] for e in entries))
    return {
        "version": 2,
        "count": len(entries),
        "areas": areas,
        "characters": characters,
        "palettes": NES_PALETTE_HEX,
        "tiles": _extract_nes_font_tiles(root),
        "strings": entries,
    }


def write_z2_strings_data_js(out_dir: Path | None = None) -> Path:
    target_dir = ROOT / "web" if out_dir is None else out_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(build_z2_strings_payload(ROOT), indent=2)
    out_path = target_dir / "local_z2_strings_data.js"
    out_path.write_text(f"window.Z2_STRINGS_DATA = {payload};\n", encoding="utf-8")
    return out_path


if __name__ == "__main__":
    p = write_z2_strings_data_js()
    print(f"Wrote {p.relative_to(ROOT)}")
