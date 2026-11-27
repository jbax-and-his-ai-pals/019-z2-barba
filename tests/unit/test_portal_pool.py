"""Unit tests for the subgame portal pool and candidate door assignment."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

import portal_pool  # noqa: E402


class PortalPoolTests(unittest.TestCase):
    def test_default_assignments_match_waldo(self) -> None:
        slots = portal_pool.build_portal_assignments()
        self.assertEqual([s.subgame.id for s in slots], ['waldo'])
        self.assertEqual(slots[0].door.id, 'arcade_waldo')

    def test_seeded_assignments_pick_distinct_doors(self) -> None:
        slots = portal_pool.build_portal_assignments(['waldo', 'feud'], seed=42)
        self.assertEqual(len(slots), 2)
        self.assertNotEqual(slots[0].door.id, slots[1].door.id)

    def test_manifest_round_trip(self) -> None:
        slots = portal_pool.build_portal_assignments()
        with tempfile.TemporaryDirectory() as tmp:
            out = portal_pool.write_portal_manifest(Path(tmp) / 'portal-manifest.json', slots, seed=7)
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(data['seed'], 7)
            self.assertEqual(len(data['slots']), 1)
            self.assertEqual(data['slots'][0]['boot']['boot_addr'], 0xE000)

    def test_no_portal_overlaps_service_spell_or_quest_doors(self) -> None:
        # (town_id, room, page) for all Zelda II spell houses, healers ($17),
        # magic-refill ladies ($18), technique knights ($15), and quest houses.
        reserved_doors: dict[tuple[int, int, int], str] = {
            (0x00, 0x01, 2): 'Rauru SCALES spell house',
            (0x00, 0x02, 0): 'Rauru healer',
            (0x01, 0x04, 3): 'Ruto JUMP spell house',
            (0x01, 0x05, 1): 'Ruto magic-refill lady',
            (0x01, 0x05, 2): 'Ruto healer',
            (0x02, 0x07, 0): 'Saria healer',
            (0x02, 0x07, 1): 'Saria magic-refill lady',
            (0x02, 0x08, 1): 'Saria LIFE spell house',
            (0x03, 0x09, 3): 'Mido Downward Thrust knight',
            (0x03, 0x0A, 0): 'Mido magic-refill lady',
            (0x03, 0x0B, 2): 'Mido healer',
            (0x04, 0x0C, 2): 'Nabooru Water of Life fountain',
            (0x04, 0x0D, 0): 'Nabooru healer',
            (0x04, 0x0D, 3): 'Nabooru FIRE spell house',
            (0x04, 0x0E, 0): 'Nabooru magic-refill lady',
            (0x04, 0x0E, 1): 'Nabooru Water of Life fountain',
            (0x05, 0x0F, 3): 'Darunia Upward Thrust knight',
            (0x05, 0x10, 3): 'Darunia REFLECT spell / child quest',
            (0x05, 0x11, 0): 'Darunia magic-refill lady',
            (0x05, 0x11, 1): 'Darunia healer',
            (0x06, 0x12, 1): 'New Kasuto SPELL house',
            (0x06, 0x12, 3): 'New Kasuto magic-refill lady',
            (0x06, 0x13, 0): 'New Kasuto healer',
            (0x06, 0x13, 1): 'New Kasuto Magic Container',
        }
        seen_locations: set[tuple[int, int, int, int]] = set()
        for door in portal_pool.CANDIDATE_DOORS:
            loc = (door.town_id, door.room, door.page)
            self.assertNotIn(
                loc,
                reserved_doors,
                f'{door.id} overlaps {reserved_doors.get(loc)}',
            )
            key = (door.town_id, door.room, door.page, door.x_lo)
            self.assertNotIn(key, seen_locations, f'Duplicate candidate door location {key}')
            seen_locations.add(key)

        all_ids = [s.id for s in portal_pool.SUBGAME_POOL]
        slots = portal_pool.build_portal_assignments(all_ids)
        seen_hyrule: set[tuple[int, int, int, int, int]] = set()
        for slot in slots:
            loc = (slot.door.town_id, slot.door.room, slot.door.page)
            self.assertNotIn(
                loc,
                reserved_doors,
                f'Subgame {slot.subgame.id} overlaps {reserved_doors.get(loc)}',
            )
            h = slot.hyrule
            h_key = (h.world, h.sub_id, h.room, h.page, h.x_lo)
            self.assertNotIn(h_key, seen_hyrule, f'Duplicate Hyrule spot {h_key}')
            seen_hyrule.add(h_key)
            if h.world in (1, 2):
                self.assertNotIn(
                    (h.sub_id, h.room, h.page),
                    reserved_doors,
                    f'Hyrule spot {h.id} overlaps {reserved_doors.get((h.sub_id, h.room, h.page))}',
                )


if __name__ == '__main__':
    unittest.main()
