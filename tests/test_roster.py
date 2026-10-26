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

    def resolve(self, order=None):
        return roster.resolve(roster.load_characters(self.dir), order)

    def test_vanilla_only_is_24(self):
        r = self.resolve()
        self.assertEqual(len(r), 24)
        self.assertEqual(r[0].name, "Mario")

    def test_custom_gets_free_id_of_its_weight(self):
        self.add("shadow", name="Shadow", weight="medium", suffix="sh", stats_like="Mario")
        self.add("tiny", name="Tiny", weight="small", suffix="ti", stats_like="Toad")
        r = {e.key: e for e in self.resolve()}
        self.assertEqual(r["shadow"].id, 0x1E)
        self.assertEqual(r["tiny"].id, 0x18)
        self.assertEqual(r["shadow"].stats_from, 0x00)

    def test_full_roster_is_48_and_49th_fails(self):
        for w, n in (("small", 7), ("medium", 9), ("large", 8)):
            for i in range(n):
                self.add(f"{w}{i}", name=f"{w}{i}", weight=w, suffix=f"{w[0]}x{i}",
                         stats_like={"small": "Toad", "medium": "Mario", "large": "Bowser"}[w])
        self.assertEqual(len(self.resolve()), 48)
        self.add("extra", name="Extra", weight="small", suffix="ex", stats_like="Toad")
        with self.assertRaisesRegex(roster.RosterError, "no free small slots"):
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

    def test_generated_table(self):
        self.add("shadow", name='Sha"dow', weight="medium", suffix="sh", stats_like="Mario")
        c = build.roster_table_c(self.resolve())
        self.assertIn('[0x1E] = {"Sha\\"dow", "sh", 0x00, 1},', c)
        self.assertIn("const u32 rosterCount = 25;", c)


if __name__ == "__main__":
    unittest.main()
