#!/usr/bin/env python3
"""Build the select-screen UI archives: the roster as rows of buttons along the
bottom and the driver previews across the top.

  python3 tools/pack_ui.py --game <extracted disc DATA/files> --out <dir>

For every Scene/UI/*.szs that contains button/ctrl/CharacterSelect4_0.brctr
(MenuSingle, MenuMulti) this:
  - adds button/ctrl/CharacterSelect48.brctr with records Button0..Button<N-1>
    placed by layout.grid(N), N = the roster size from tools/roster.py;
  - moves the CharacterSelectModel previews (1P, 2P, 4P) to layout.preview_row
    and the CharacterSelectName plates just under each preview;
  - sets the CharacterSelectNULL / ...Center offset to (0, 0) at scale 1, so
    the button placements are screen positions;
and writes the repacked archive to <out>/files/Scene/UI/. The output is
derived from game files: keep it out of the repository.

Needs Wiimm's SZS Tools (wszst): on PATH, in $WSZST, or passed with --wszst.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brctr  # noqa: E402
import layout  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = "button/ctrl/CharacterSelect4_0.brctr"
GRID_CTR = "button/ctrl/CharacterSelect48.brctr"
MODEL_CTR = "model/ctrl/CharacterSelectModel.brctr"
NAME_CTR = "control/ctrl/CharacterSelectName.brctr"
NULL_CTR = "control/ctrl/CharacterSelectNULL.brctr"
ASPECTS = (("4:3", "wide4_3"), ("16:9", "wide16_9"))
# preview variants per local player count, and the matching name plates
PREVIEWS = {
    1: (["1P_1Div"], ["CharacterSelectName"]),
    2: (["1P_2Div", "2P_2Div"], ["CharacterSelectName1P2", "CharacterSelectName2P2"]),
    4: (["1P_4Div", "2P_4Div", "3P_4Div", "4P_4Div"],
        ["CharacterSelectName1P4", "CharacterSelectName2P4", "CharacterSelectName3P4", "CharacterSelectName4P4"]),
}


def find_wszst(arg):
    for cand in (arg, os.environ.get("WSZST"), shutil.which("wszst")):
        if cand and Path(cand).exists() or (cand and shutil.which(cand)):
            return cand
    sys.exit("wszst not found: install Wiimm's SZS Tools, or pass --wszst / set WSZST")


def roster_size():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "roster.py"), "--json"],
                         check=True, capture_output=True, text=True).stdout
    import json
    return len(json.loads(out))


def place(rec, aspect_attr, p, scale=None):
    pl = getattr(rec, aspect_attr)
    pl.x, pl.y = p.x, p.y
    s = p.scale if scale is None else scale
    pl.scale_x = pl.scale_y = s


def build_grid(template_path, count):
    ctr = brctr.load(template_path)
    ctr.records = []
    grids = {aspect: layout.grid(count, aspect=aspect) for aspect, _ in ASPECTS}
    for i in range(count):
        rec = brctr.Record(f"Button{i}")
        for aspect, attr in ASPECTS:
            place(rec, attr, grids[aspect][i])
        ctr.set(rec)
    return ctr


def move_previews(model_path, name_path):
    model, names = brctr.load(model_path), brctr.load(name_path)
    for players, (model_vars, name_vars) in PREVIEWS.items():
        for aspect, attr in ASPECTS:
            row = layout.preview_row(players, aspect=aspect)
            for i, p in enumerate(row):
                rec = model.get(model_vars[i])
                if rec:
                    place(rec, attr, p)
                rec = names.get(name_vars[i])
                if rec:
                    plate_scale = min(0.8, p.scale)
                    under = layout.Placement(layout.preview_x(players, i, aspect), round(layout.name_plate_y(plate_scale), 2), plate_scale)
                    place(rec, attr, under)
    return model, names


def zero_null(null_path):
    ctr = brctr.load(null_path)
    for rec in ctr.records:
        if rec.name.startswith("CharacterSelectNULL"):
            for _, attr in ASPECTS:
                place(rec, attr, layout.Placement(0, 0, 1.0))
    return ctr


def pack_archive(wszst, src, dest, count, work):
    d = Path(work) / (src.stem + ".d")
    subprocess.run([wszst, "extract", "-q", "-o", str(src), "-d", str(d)], check=True)
    if not (d / TEMPLATE).exists():
        return False
    brctr.save(build_grid(d / TEMPLATE, count), d / GRID_CTR)
    if (d / MODEL_CTR).exists() and (d / NAME_CTR).exists():
        model, names = move_previews(d / MODEL_CTR, d / NAME_CTR)
        brctr.save(model, d / MODEL_CTR)
        brctr.save(names, d / NAME_CTR)
    if (d / NULL_CTR).exists():
        brctr.save(zero_null(d / NULL_CTR), d / NULL_CTR)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([wszst, "create", "-q", "-o", str(d), "-d", str(dest)], check=True)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True, help="extracted disc files/ folder (holds Scene/)")
    ap.add_argument("--out", required=True, help="output folder; archives go to <out>/files/Scene/UI/")
    ap.add_argument("--count", type=int, help="number of buttons (default: roster size)")
    ap.add_argument("--wszst", help="path to wszst")
    args = ap.parse_args(argv)
    wszst = find_wszst(args.wszst)
    count = args.count or roster_size()
    ui = Path(args.game) / "Scene" / "UI"
    out = Path(args.out) / "files" / "Scene" / "UI"
    with tempfile.TemporaryDirectory() as work:
        done = [src.name for src in sorted(ui.glob("*.szs"))
                if pack_archive(wszst, src, out / src.name, count, work)]
    if not done:
        sys.exit(f"no archive under {ui} has {TEMPLATE}")
    print(f"{count} buttons; wrote {', '.join(done)} to {out}")


if __name__ == "__main__":
    main()
