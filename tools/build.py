#!/usr/bin/env python3
"""Build the mod for Riivolution: resolve the roster from characters/ and
roster.toml, write it to roster48.bin, and put the prebuilt game code patch
and the Riivolution XML next to it. Needs only Python 3.11+.

  python3 tools/build.py [--variant RMCE01] [--out out]

Then run tools/pack_ui.py and tools/pack_assets.py (they need your extracted
game and Wiimm's SZS tools) to add the select-screen layout and each custom
character's files, and copy everything in out/ to your SD card or Dolphin's
Load/Riivolution folder.
"""

import argparse
import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster as roster_mod  # noqa: E402
from ids import MAX_CHARACTERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREBUILT = ROOT / "prebuilt"
MOD_ID = "mkw-48-roster"

# Must match struct RosterFile in payload/include/roster_table.h.
ROSTER_MAGIC = 0x52343801
SUFFIX_LEN, ICON_LEN = 8, 20
ENTRY = struct.Struct(f">{SUFFIX_LEN}s{ICON_LEN}sBB2x")
FILE_SIZE = 8 + MAX_CHARACTERS + MAX_CHARACTERS * ENTRY.size + 8


class BuildError(Exception):
    pass


def icon_pane(suffix):
    return f"cha_x_{suffix}"


def roster_bin(entries):
    """The roster file the payload reads at boot."""
    by_id = {e.id: e for e in entries}
    out = bytearray(struct.pack(">II", ROSTER_MAGIC, len(entries)))
    out += bytes(e.id for e in entries).ljust(MAX_CHARACTERS, b"\0")
    for cid in range(MAX_CHARACTERS):
        e = by_id.get(cid)
        if e and e.custom:
            out += ENTRY.pack(e.suffix.encode(), icon_pane(e.suffix).encode(), e.stats_from, 1)
        else:  # vanilla or unused: the hooks fall back to the game's own data
            out += ENTRY.pack(b"", b"", cid if cid < 24 else 0, 0)
    out += bytes(FILE_SIZE - len(out))
    assert len(out) == FILE_SIZE and FILE_SIZE % 32 == 0
    return bytes(out)


def branch(src, dst):
    return 0x48000000 | ((dst - src) & 0x03FFFFFC)


def riivolution_xml(info):
    region, syms = info["region"], info["symbols"]
    hook, base, original = info["loader_hook"], info["load_address"], info["loader_hook_original"]
    return f"""<wiidisc version="1">
\t<id game="{region[:4]}" />
\t<options>
\t\t<section name="48 Roster">
\t\t\t<option name="48 Roster">
\t\t\t\t<choice name="Enabled"><patch id="roster48" /></choice>
\t\t\t</option>
\t\t</section>
\t</options>
\t<patch id="roster48">
\t\t<memory offset="0x{base:08X}" valuefile="/{MOD_ID}/code/payload-{region}.bin" />
\t\t<memory offset="0x{syms['roster_replaced_insn']:08X}" value="{original:08X}" />
\t\t<memory offset="0x{syms['roster_return']:08X}" value="{branch(syms['roster_return'], hook + 4):08X}" />
\t\t<memory offset="0x{hook:08X}" value="{branch(hook, syms['roster_entry']):08X}" original="{original:08X}" />
\t\t<folder external="/{MOD_ID}/files" disc="/" create="true" recursive="true" />
\t</patch>
</wiidisc>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="RMCE01", help="folder in prebuilt/, e.g. RMCE01 or RMCE01-debug")
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args(argv)
    try:
        entries = roster_mod.resolve(roster_mod.load_characters(), roster_mod.load_order())
        pre = PREBUILT / args.variant
        if not (pre / "payload.json").exists():
            raise BuildError(f"{pre} has no prebuilt payload; run tools/compile_payload.py first")
        info = json.loads((pre / "payload.json").read_text())
        out = Path(args.out)
        files = out / MOD_ID / "files"
        files.mkdir(parents=True, exist_ok=True)
        (files / "roster48.bin").write_bytes(roster_bin(entries))
        code = out / MOD_ID / "code"
        code.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pre / "payload.bin", code / f"payload-{info['region']}.bin")
        riiv = out / "riivolution"
        riiv.mkdir(parents=True, exist_ok=True)
        (riiv / f"{MOD_ID}.xml").write_text(riivolution_xml(info))
    except (roster_mod.RosterError, BuildError) as e:
        print("error: " + str(e).replace("\n", "\nerror: "), file=sys.stderr)
        return 1
    custom = sum(e.custom for e in entries)
    print(f"Built {len(entries)}/{MAX_CHARACTERS} characters ({custom} custom) into {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
