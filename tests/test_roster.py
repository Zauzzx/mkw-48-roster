"""Run with: python3 -m unittest discover tests"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import build  # noqa: E402
import roster  # noqa: E402


class RosterTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def add(self, folder, **cfg):
        d = self.dir / folder
        d.mkdir()
        body = "".join(f"{k} = {json.dumps(v)}\n" for k, v in cfg.items())
        (d / "character.toml").write_text(body)

    def resolve(self, order=None, miis=True):
        return roster.resolve(roster.load_characters(self.dir), order, miis)

    def test_vanilla_only_is_24(self):
        r = self.resolve()
        self.assertEqual(len(r), 24)
        self.assertEqual(r[0].name, "Mario")

    def test_custom_gets_free_id_of_its_weight(self):
        self.add("shadow", name="Shadow", weight="medium", suffix="sh", stats_like="Mario")
        self.add("tiny", name="Tiny", weight="small", suffix="ti", stats_like="Toad")
        r = {e.key: e for e in self.resolve()}
        # 0x1E and 0x18 are kept for Miis
        self.assertEqual(r["shadow"].id, 0x20)
        self.assertEqual(r["tiny"].id, 0x1A)
        self.assertEqual(r["shadow"].stats_from, 0x00)
        r = {e.key: e for e in self.resolve(miis=False)}
        self.assertEqual((r["shadow"].id, r["tiny"].id), (0x1E, 0x18))

    def fill(self, counts):
        for w, n in zip(("small", "medium", "large"), counts):
            for i in range(n):
                self.add(f"{w}{i}", name=f"{w}{i}", weight=w, suffix=f"{w[0]}x{i}",
                         stats_like={"small": "Toad", "medium": "Mario", "large": "Bowser"}[w])

    def test_full_roster_is_48_and_49th_fails(self):
        self.fill((7, 9, 8))
        self.assertEqual(len(self.resolve(miis=False)), 48)
        self.add("extra", name="Extra", weight="small", suffix="ex", stats_like="Toad")
        with self.assertRaisesRegex(roster.RosterError, r"no free small slots left \(there are 7 small, 9 medium, 8 large"):
            self.resolve(miis=False)

    def test_miis_leave_18_slots(self):
        self.fill((5, 7, 6))
        r = self.resolve()
        self.assertEqual(len(r), 42)
        self.assertFalse({e.id for e in r} & set(roster.MII_IDS))
        self.add("extra", name="Extra", weight="large", suffix="ex", stats_like="Bowser")
        with self.assertRaisesRegex(roster.RosterError, r"no free large slots left \(there are 5 small, 7 medium, 6 large"):
            self.resolve()

    def test_replace_vanilla(self):
        self.add("shadow", name="Shadow", replaces="Waluigi", suffix="sh")
        r = self.resolve()
        self.assertEqual(len(r), 24)
        sh = next(e for e in r if e.key == "shadow")
        self.assertEqual((sh.id, sh.weight, sh.stats_from), (0x02, "large", 0x02))
        self.assertNotIn("Waluigi", [e.name for e in r])

    def test_errors(self):
        self.add("a", name="A", weight="medium", suffix="mr", stats_like="Mario")  # suffix taken
        self.add("b", name="B", weight="huge", suffix="bb", stats_like="Mario")
        self.add("c", name="C", weight="small", suffix="cc", stats_like="Mario")  # wrong weight
        with self.assertRaises(roster.RosterError) as cm:
            self.resolve()
        msg = str(cm.exception)
        self.assertIn("already used by Mario", msg)
        self.assertIn("weight must be", msg)
        self.assertIn("is medium, but", msg)

    def test_order(self):
        self.add("shadow", name="Shadow", weight="medium", suffix="sh", stats_like="Mario")
        r = self.resolve(["shadow", "Luigi"])
        self.assertEqual([e.name for e in r[:3]], ["Shadow", "Luigi", "Mario"])

    def test_roster_bin(self):
        import struct
        self.add("shadow", name="Shadow", weight="medium", suffix="sh", stats_like="Mario")
        data = build.roster_bin(self.resolve())
        self.assertEqual(len(data), 1600)  # sizeof(struct RosterFile)
        magic, count = struct.unpack_from(">II", data)
        self.assertEqual((magic, count), (0x52343801, 25))
        self.assertEqual(data[8 + 24], 0x20)  # the 25th button is Shadow
        suffix, icon, stats, custom = build.ENTRY.unpack_from(data, 8 + 48 + 0x20 * 32)
        self.assertEqual((suffix.rstrip(b"\0"), icon.rstrip(b"\0"), stats, custom), (b"sh", b"cha_x_sh", 0, 1))
        self.assertEqual(data[8 + 48 + 48 * 32], 0x21)  # flags: unlock_all | miis
        self.assertEqual(build.roster_bin(self.resolve(miis=False), miis=False)[8 + 48 + 48 * 32], 0x01)


if __name__ == "__main__":
    unittest.main()
