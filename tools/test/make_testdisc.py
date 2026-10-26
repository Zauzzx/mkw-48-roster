"""Apply a Riivolution XML's <memory> patches to an extracted disc's main.dol.

Riivolution writes its memory patches after the apploader has loaded main.dol
and before the game starts, so writing the same bytes into the DOL's sections
gives the same result. This lets Dolphin boot the extracted disc folder
(Dolphin.exe -e <disc>/sys/main.dol) without the Riivolution GUI.

Usage: python make_testdisc.py <riivolution.xml> <riivolution root> <base main.dol> <out main.dol>
           [--overlay <dir with files/>]...

--overlay copies <dir>/files/** over the extracted disc's files/ (the disc is
the folder above the output main.dol's sys/). Originals are backed up to
<disc>/_orig/ the first time they are replaced and every earlier overlay is
undone first, so each run starts from the vanilla disc plus this run's
overlays.

<riivolution root> is the folder that valuefile paths are relative to (the one
that holds mkw-48-roster/). Only <memory> patches are applied; <folder>/<file>
patches must be copied into the disc's files/ by hand.
"""
import argparse
import shutil
import struct
import xml.etree.ElementTree as ET
from pathlib import Path


def dol_sections(dol):
    off = struct.unpack(">18I", dol[0:72])
    addr = struct.unpack(">18I", dol[72:144])
    size = struct.unpack(">18I", dol[144:216])
    return [(off[i], addr[i], size[i]) for i in range(18) if size[i]]


def write_mem(dol, addr, data):
    for off, start, size in dol_sections(dol):
        if start <= addr and addr + len(data) <= start + size:
            p = off + addr - start
            dol[p:p + len(data)] = data
            return
    raise ValueError(f"0x{addr:08X}+{len(data):#x} is not inside one DOL section")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml")
    ap.add_argument("root")
    ap.add_argument("dol_in")
    ap.add_argument("dol_out")
    ap.add_argument("--overlay", action="append", default=[])
    args = ap.parse_args()
    dol = bytearray(Path(args.dol_in).read_bytes())
    root = Path(args.root)
    for mem in ET.parse(args.xml).getroot().iter("memory"):
        addr = int(mem.get("offset"), 16)
        if mem.get("valuefile"):
            data = (root / mem.get("valuefile").lstrip("/")).read_bytes()
        else:
            data = bytes.fromhex(mem.get("value"))
        if mem.get("original"):
            orig = bytes.fromhex(mem.get("original"))
            cur = next(bytes(dol[o + addr - s:o + addr - s + len(orig)])
                       for o, s, z in dol_sections(dol) if s <= addr < s + z)
            if cur != orig:
                raise SystemExit(f"0x{addr:08X}: expected {orig.hex()} but DOL has {cur.hex()}")
        write_mem(dol, addr, data)
        print(f"patched 0x{addr:08X} ({len(data)} bytes)")
    Path(args.dol_out).write_bytes(dol)
    apply_overlays(Path(args.dol_out).resolve().parent.parent, [Path(o) for o in args.overlay])


def apply_overlays(disc, overlays):
    files, backup = disc / "files", disc / "_orig"
    added = disc / "_added.txt"
    # undo earlier overlays
    if backup.exists():
        for f in backup.rglob("*"):
            if f.is_file():
                shutil.copy2(f, files / f.relative_to(backup))
    if added.exists():
        for rel in added.read_text().splitlines():
            if rel and (files / rel).exists():
                (files / rel).unlink()
        added.unlink()
    new = []
    for ov in overlays:
        src = ov / "files"
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src)
            dst = files / rel
            if dst.exists():
                if not (backup / rel).exists():
                    (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst, backup / rel)
            else:
                new.append(rel.as_posix())
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
            print(f"overlay {rel.as_posix()}")
    if new:
        added.write_text("\n".join(new))


if __name__ == "__main__":
    main()
