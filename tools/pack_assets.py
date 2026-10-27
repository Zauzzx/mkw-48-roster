#!/usr/bin/env python3
"""Pack the custom characters' game files.

  python3 tools/pack_assets.py --game <extracted disc DATA/files> --out <dir>

For every custom character from tools/roster.py (weight w, suffix s), files
from its folder characters/<name>/ go where the game looks for them:

  kart/<archive>.szs     Race/Kart/<archive>-<s>.szs and Scene/Model/Kart/<s>-allkart*.szs.
                         The expected names come from the vanilla files of a
                         reference driver of the same weight (small: Toad "ko",
                         medium: Mario "mr", large: Bowser "kp"). In kart/ a file
                         may be named either way: ma_kart-<s>.szs or ma_kart.szs,
                         ma_kart_2.szs, allkart.szs, allkart_BT.szs.
  menu/model.brres       <s>.brres inside Scene/Model/Driver.szs (the menu preview).
  icon.png               64x64 icon: texture tt_<s>_64x64.tpl plus a picture pane
                         "cha_x_<s>" in character_64x64_common.brlyt, and the same
                         icon as tt_<s>_32x32.tpl / "cha_x_<s>" in the race minimap's
                         character_map_icon_common.brlyt, in every UI
                         archive that has that layout.
  name (character.toml)  BMG message 0x2328+id in every Common.bmg that holds the
                         vanilla driver names (one per language archive).

With the speedometer on in roster.toml, its layout (assets/speedometer/, from
Pulsar) and digit textures (speedometer/*.tpl, e.g. one colour of the
Speedometer Recolor Pack) are added to Scene/UI/Race.szs under game_image/.

With clone_from = "<Vanilla Name>" in character.toml, anything missing is copied
from that vanilla driver (for placeholders and tests; such output must never be
committed). Output goes to <out>/files/..., laid out like the disc. Archives
already in <out> (from tools/pack_ui.py) are used as the starting point, so the
two tools can run in either order.

Needs Wiimm's SZS Tools: wszst, wbmgt, wimgt (on PATH, or WSZST/WBMGT/WIMGT, or
--szs-bin <folder>).
"""

import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ids import VANILLA  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = {"small": "ko", "medium": "mr", "large": "kp"}
# vanilla menu-preview models that differ from the race postfix
MENU_MODEL = {"pc": "pc_menu", "ds": "ds_menu", "rs": "rs_menu"}
# icon layouts -> texture size in the name; the game looks a character's icon
# pane up by the same name (GetCharacterIconPaneName) in each of them
ICON_LAYOUTS = {"character_64x64_common.brlyt": "64x64", "character_map_icon_common.brlyt": "32x32"}
NAME_BMG_BASE = 0x2328
SPEEDO_LAYOUT = {"PULSpeedo.brctr": "ctrl", "PULSpeedo.brlyt": "blyt", "PULSpeedo.brlan": "anim"}
SPEEDO_TEXTURES = [f"som_d_number_3d_{i:02d}.tpl" for i in range(10)] + [
    "som_d_number_3d_coron.tpl", "som_d_none.tpl", "speed.tpl"]
PIC_MAT_OFF = 0x5C  # pic1 section: 8 header + 0x44 pane + 0x10 vertex colours, then u16 material
# vanilla icon pane per character ID (from the game's icon pane table)
VANILLA_ICON = ["cha_01_mario", "cha_19_baby_p", "cha_13_waluiji", "cha_04_koopa", "cha_18_baby_d",
                "cha_17_karon", "cha_09_baby_m", "cha_02_luiji", "cha_23_kinopio", "cha_05_donky",
                "cha_11_yoshi", "cha_12_wario", "cha_10_baby_l", "cha_24_kinopiko", "cha_16_noko",
                "cha_07_daisy", "cha_14_peach", "cha_08_catherine", "cha_06_didy", "cha_22_teresa",
                "cha_03_koopa_jr", "cha_25_h_koopa", "cha_30_funky", "cha_31_rosetta"]


class PackError(Exception):
    pass


# ---------------------------------------------------------------- tools

class Tools:
    def __init__(self, szs_bin=None):
        self.paths = {}
        for name in ("wszst", "wbmgt", "wimgt"):
            cands = [Path(szs_bin) / f"{name}.exe" if szs_bin else None,
                     Path(szs_bin) / name if szs_bin else None,
                     os.environ.get(name.upper()), shutil.which(name)]
            found = next((str(c) for c in cands if c and Path(c).exists()), None)
            if not found:
                raise PackError(f"{name} not found: install Wiimm's SZS Tools or pass --szs-bin")
            self.paths[name] = found

    def run(self, name, *args):
        subprocess.run([self.paths[name], *map(str, args)], check=True)

    def extract(self, szs, dest):
        self.run("wszst", "extract", "-q", "-o", szs, "-d", dest)

    def create(self, src_dir, szs):
        Path(szs).parent.mkdir(parents=True, exist_ok=True)
        self.run("wszst", "create", "-q", "-o", src_dir, "-d", szs)


# ---------------------------------------------------------------- BRLYT

def _sections(data):
    off = struct.unpack_from(">H", data, 0x0C)[0]
    count = struct.unpack_from(">H", data, 0x0E)[0]
    out = []
    for _ in range(count):
        magic = data[off:off + 4].decode("ascii")
        size = struct.unpack_from(">I", data, off + 4)[0]
        out.append([magic, bytearray(data[off:off + size])])
        off += size
    return struct.unpack_from(">H", data, 0x0C)[0], out


def _join(head, sections):
    body = b"".join(bytes(s) for _, s in sections)
    head = bytearray(head)
    struct.pack_into(">I", head, 0x08, len(head) + len(body))
    struct.pack_into(">H", head, 0x0E, len(sections))
    return bytes(head) + body


def _txl_names(sec):
    n = struct.unpack_from(">H", sec, 8)[0]
    base = 12
    names = []
    for i in range(n):
        o = struct.unpack_from(">I", sec, base + 8 * i)[0]
        e = sec.index(0, base + o)
        names.append(sec[base + o:e].decode("ascii"))
    return names


def _txl_build(names):
    n = len(names)
    table = bytearray()
    strings = bytearray()
    for name in names:
        table += struct.pack(">II", 8 * n + len(strings), 0)
        strings += name.encode("ascii") + b"\0"
    body = struct.pack(">HH", n, 0) + table + strings
    body += bytes(-(8 + len(body)) % 4)
    return bytearray(b"txl1" + struct.pack(">I", 8 + len(body)) + body)


def _mat_entries(sec):
    n = struct.unpack_from(">H", sec, 8)[0]
    offs = [struct.unpack_from(">I", sec, 12 + 4 * i)[0] for i in range(n)] + [len(sec)]
    return [bytearray(sec[offs[i]:offs[i + 1]]) for i in range(n)]


def _mat_build(mats):
    n = len(mats)
    head = 12 + 4 * n
    offs, o = [], head
    for m in mats:
        offs.append(o)
        o += len(m)
    body = struct.pack(">HH", n, 0) + b"".join(struct.pack(">I", x) for x in offs) + b"".join(bytes(m) for m in mats)
    return bytearray(b"mat1" + struct.pack(">I", 8 + len(body)) + body)


def _pane_name(sec):
    return sec[12:28].split(b"\0")[0].decode("ascii")


def add_icon_pane(layout_bytes, pane, texture, template_pane):
    """Return the layout with a new picture pane `pane` showing `texture`,
    cloned from `template_pane` (with its own material). No-op if present."""
    head_len, secs = _sections(layout_bytes)
    head = layout_bytes[:head_len]
    if any(m == "pic1" and _pane_name(s) == pane for m, s in secs):
        return layout_bytes
    ti = next(i for i, (m, _) in enumerate(secs) if m == "txl1")
    mi = next(i for i, (m, _) in enumerate(secs) if m == "mat1")
    names = _txl_names(secs[ti][1])
    if texture not in names:
        names.append(texture)
    tex_index = names.index(texture)
    secs[ti][1] = _txl_build(names)
    mats = _mat_entries(secs[mi][1])
    src_i, src = next((i, s) for i, (m, s) in enumerate(secs) if m == "pic1" and _pane_name(s) == template_pane)
    src_mat = struct.unpack_from(">H", src, PIC_MAT_OFF)[0]
    mat = bytearray(mats[src_mat])
    mat[0:20] = pane.encode("ascii")[:19].ljust(20, b"\0")
    if struct.unpack_from(">I", mat, 0x3C)[0] & 0xF < 1:
        raise PackError(f"material of {template_pane} has no texture map")
    struct.pack_into(">H", mat, 0x40, tex_index)
    mats.append(mat)
    secs[mi][1] = _mat_build(mats)
    pic = bytearray(src)
    pic[12:28] = pane.encode("ascii")[:15].ljust(16, b"\0")
    struct.pack_into(">H", pic, PIC_MAT_OFF, len(mats) - 1)
    secs.insert(src_i + 1, ["pic1", pic])
    return _join(head, secs)


def pane_texture(layout_bytes, pane):
    _, secs = _sections(layout_bytes)
    names = _txl_names(next(s for m, s in secs if m == "txl1"))
    mats = _mat_entries(next(s for m, s in secs if m == "mat1"))
    pic = next(s for m, s in secs if m == "pic1" and _pane_name(s) == pane)
    mat = mats[struct.unpack_from(">H", pic, PIC_MAT_OFF)[0]]
    return names[struct.unpack_from(">H", mat, 0x40)[0]]


# ---------------------------------------------------------------- roster

def custom_characters():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "roster.py"), "--json"],
                         check=True, capture_output=True, text=True).stdout
    chars = []
    for e in json.loads(out):
        if not e["custom"]:
            continue
        cfg = tomllib.loads((Path(e["folder"]) / "character.toml").read_text(encoding="utf-8"))
        clone = cfg.get("clone_from")
        if clone is not None and clone not in VANILLA:
            raise PackError(f"{e['key']}: clone_from {clone!r} is not a vanilla character")
        e["clone"] = clone
        chars.append(e)
    return chars


def pick(folder, names):
    for n in names:
        p = Path(folder) / n
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------- packers

def pack_karts(game, out, ch, missing):
    ref = REFERENCE[ch["weight"]]
    s, clone = ch["suffix"], ch["clone"]
    clone_suffix = VANILLA[clone][2] if clone else None
    if clone and VANILLA[clone][1] != ch["weight"]:
        raise PackError(f"{ch['key']}: clone_from {clone} has a different weight")
    pattern = re.compile(rf"^(.+)-{ref}(_\w+)?\.szs$")
    for f in sorted((game / "Race" / "Kart").glob(f"*-{ref}*.szs")):
        m = pattern.match(f.name)
        if not m:
            continue
        kart, variant = m.group(1), m.group(2) or ""
        target = f"{kart}-{s}{variant}.szs"
        src = pick(Path(ch["folder"]) / "kart", [target, f"{kart}{variant}.szs"])
        if not src and clone:
            src = game / "Race" / "Kart" / f"{kart}-{clone_suffix}{variant}.szs"
        _copy_or_miss(src, out / "files" / "Race" / "Kart" / target, ch, target, missing)
    for f in sorted((game / "Scene" / "Model" / "Kart").glob(f"{ref}-allkart*.szs")):
        rest = f.name[len(ref):]               # "-allkart.szs", "-allkart_BT.szs"
        target = f"{s}{rest}"
        src = pick(Path(ch["folder"]) / "kart", [target, rest[1:]])
        if not src and clone:
            src = game / "Scene" / "Model" / "Kart" / f"{clone_suffix}{rest}"
        _copy_or_miss(src, out / "files" / "Scene" / "Model" / "Kart" / target, ch, target, missing)


def _copy_or_miss(src, dst, ch, what, missing):
    if src and Path(src).exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    else:
        missing.append(f"{ch['key']}: {what}")


def start_archive(tools, game, out, rel, work):
    """Extract <out>/<rel> if a previous step wrote it, else the game's copy."""
    src = out / "files" / rel if (out / "files" / rel).exists() else game / rel
    d = Path(work) / rel.replace("/", "_")
    if d.exists():
        shutil.rmtree(d)
    tools.extract(src, d)
    return d


def pack_menu_models(tools, game, out, chars, missing, work):
    rel = "Scene/Model/Driver.szs"
    d = start_archive(tools, game, out, rel, work)
    for ch in chars:
        src = pick(Path(ch["folder"]) / "menu", ["model.brres", f"{ch['suffix']}.brres"])
        if not src and ch["clone"]:
            cs = VANILLA[ch["clone"]][2]
            src = d / f"{MENU_MODEL.get(cs, cs)}.brres"
        _copy_or_miss(src, d / f"{ch['suffix']}.brres", ch, "menu/model.brres", missing)
    tools.create(d, out / "files" / rel)


def pack_icons(tools, game, out, chars, missing, work):
    ui = game / "Scene" / "UI"
    for archive in sorted(ui.glob("*.szs")):
        if re.search(r"_[A-Z]\.szs$", archive.name):
            continue  # language archives hold only messages
        rel = f"Scene/UI/{archive.name}"
        d = start_archive(tools, game, out, rel, work)
        layouts = [lay for name in ICON_LAYOUTS for lay in d.glob(f"*/blyt/{name}")]
        if not layouts:
            continue
        for lay in layouts:
            data = lay.read_bytes()
            timg = lay.parent.parent / "timg"
            for ch in chars:
                s = ch["suffix"]
                # a picture pane scales its texture, so icon.png serves both sizes
                tex = f"tt_{s}_{ICON_LAYOUTS[lay.name]}.tpl"
                png = Path(ch["folder"]) / "icon.png"
                if png.exists():
                    tools.run("wimgt", "encode", "-q", "-o", png, "-x", "TPL.RGB5A3", "-d", timg / tex)
                elif ch["clone"]:
                    vt = pane_texture(data, VANILLA_ICON[VANILLA[ch["clone"]][0]])
                    shutil.copy2(timg / vt, timg / tex)
                else:
                    missing.append(f"{ch['key']}: icon.png")
                    continue
                data = add_icon_pane(data, f"cha_x_{s}", tex, "cha_01_mario")
            lay.write_bytes(data)
        tools.create(d, out / "files" / rel)


def pack_names(tools, game, out, chars, work):
    ui = game / "Scene" / "UI"
    done = []
    for archive in sorted(ui.glob("*_?.szs")):
        rel = f"Scene/UI/{archive.name}"
        d = start_archive(tools, game, out, rel, work)
        bmg = d / "message" / "Common.bmg"
        if not bmg.exists():
            continue
        txt = Path(work) / (archive.stem + "_Common.txt")
        tools.run("wbmgt", "decode", "-q", "-o", bmg, "-d", txt)
        lines = txt.read_text(encoding="utf-8").splitlines()
        if not any(re.match(rf"\s*{NAME_BMG_BASE:x}\s*=", ln) for ln in lines):
            continue
        for ch in chars:
            mid = f"{NAME_BMG_BASE + ch['id']:x}"
            new = f"  {mid}\t= {ch['name']}"
            idx = next((i for i, ln in enumerate(lines) if re.match(rf"\s*{mid}\s*=", ln)), None)
            if idx is None:
                lines.append(new)
            else:
                lines[idx] = new
        txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tools.run("wbmgt", "encode", "-q", "-o", txt, "-d", bmg)
        tools.create(d, out / "files" / rel)
        done.append(archive.name)
    return done


def speedometer_on():
    path = ROOT / "roster.toml"
    settings = tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return settings.get("speedometer", "left") is not False


def pack_speedometer(tools, game, out, work):
    src = ROOT / "speedometer"
    missing = [n for n in SPEEDO_TEXTURES if not (src / n).exists()]
    if missing:
        raise PackError("the speedometer needs these textures in speedometer/ (copy one colour folder of the "
                        "Speedometer Recolor Pack there, or set speedometer = false in roster.toml):\n  "
                        + "\n  ".join(missing))
    rel = "Scene/UI/Race.szs"
    d = start_archive(tools, game, out, rel, work)
    for name, sub in SPEEDO_LAYOUT.items():
        (d / "game_image" / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "assets" / "speedometer" / name, d / "game_image" / sub / name)
    for name in SPEEDO_TEXTURES:
        shutil.copy2(src / name, d / "game_image" / "timg" / name)
    tools.create(d, out / "files" / rel)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, help="extracted disc files/ folder (holds Race/, Scene/)")
    ap.add_argument("--out", required=True, help="output folder; files go to <out>/files/...")
    ap.add_argument("--szs-bin", help="folder with wszst, wbmgt and wimgt")
    args = ap.parse_args(argv)
    game, out = Path(args.game), Path(args.out)
    try:
        tools = Tools(args.szs_bin)
        chars = custom_characters()
        speedo = speedometer_on()
        missing, langs = [], []
        with tempfile.TemporaryDirectory() as work:
            if chars:
                for ch in chars:
                    pack_karts(game, out, ch, missing)
                pack_menu_models(tools, game, out, chars, missing, work)
                pack_icons(tools, game, out, chars, missing, work)
                langs = pack_names(tools, game, out, chars, work)
            if speedo:
                pack_speedometer(tools, game, out, work)
        if missing:
            raise PackError("missing files (add them, or set clone_from):\n  " + "\n  ".join(missing))
    except PackError as e:
        sys.exit(str(e))
    if chars:
        print(f"packed {', '.join(c['name'] for c in chars)}; names in {', '.join(langs)}")
    else:
        print("no custom characters")
    if speedo:
        print("added the speedometer to Scene/UI/Race.szs")


if __name__ == "__main__":
    main()
