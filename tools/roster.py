#!/usr/bin/env python3
"""Resolve the roster: read every characters/<folder>/character.toml, give each
character one of the game's 48 character IDs, and decide the button order.

  python3 tools/roster.py          print the resolved roster
  python3 tools/roster.py --json   same, as JSON (used by the build)
"""

import argparse
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ids import FREE_IDS, IDS, MAX_CHARACTERS, VANILLA, WEIGHTS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHAR_DIR = ROOT / "characters"
ROSTER_FILE = ROOT / "roster.toml"

SUFFIX_RE = re.compile(r"[a-z][a-z0-9]{1,5}")
MAX_NAME = 20


class RosterError(Exception):
    pass


@dataclass
class Entry:
    id: int            # game character ID, 0x00-0x2F
    key: str           # folder name, or the vanilla name for untouched vanilla drivers
    name: str
    weight: str
    suffix: str        # file suffix, e.g. "mr" in st_kart-mr.szs
    stats_from: int    # ID whose stats this character copies
    custom: bool       # False for a vanilla driver left as-is
    folder: str = ""


def _vanilla_entries():
    return {vanilla: Entry(i, vanilla, vanilla, weight, suffix, i, False)
            for vanilla, (i, weight, suffix) in VANILLA.items()}


def load_characters(char_dir=None):
    char_dir = char_dir or CHAR_DIR
    chars = []
    for folder in sorted(p for p in char_dir.iterdir() if p.is_dir() and not p.name.startswith("_")):
        cfg_path = folder / "character.toml"
        if not cfg_path.exists():
            continue
        try:
            cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise RosterError(f"{cfg_path}: {e}") from e
        if cfg.get("enabled", True):
            chars.append((folder, cfg))
    return chars


def resolve(chars, order=None):
    """Assign IDs and button order. Returns the list of entries in button order."""
    errors = []
    vanilla = _vanilla_entries()
    by_id = {e.id: e for e in vanilla.values()}
    free = {w: [i for i, fw in FREE_IDS if fw == w] for w in WEIGHTS}
    suffixes = {e.suffix: e.name for e in vanilla.values()}
    customs = []

    for folder, cfg in chars:
        key = folder.name
        name = cfg.get("name", "")
        if not name.strip():
            errors.append(f"{key}: name is missing")
            continue
        if len(name) > MAX_NAME:
            errors.append(f"{key}: name {name!r} is longer than {MAX_NAME} characters")
        replaces = cfg.get("replaces")
        if replaces is not None and replaces not in vanilla:
            errors.append(f"{key}: replaces {replaces!r} is not a vanilla character ({', '.join(vanilla)})")
            continue
        weight = cfg.get("weight", vanilla[replaces].weight if replaces else None)
        if weight not in WEIGHTS:
            errors.append(f"{key}: weight must be one of {', '.join(WEIGHTS)}")
            continue
        if replaces and weight != vanilla[replaces].weight:
            errors.append(f"{key}: replacing {replaces} means weight {vanilla[replaces].weight}, not {weight}")
            continue
        suffix = cfg.get("suffix", "")
        if not SUFFIX_RE.fullmatch(suffix):
            errors.append(f"{key}: suffix {suffix!r} must be 2-6 lowercase letters/digits, starting with a letter")
            continue
        if replaces:
            target = vanilla.pop(replaces)
            if suffix != target.suffix:
                suffixes.pop(target.suffix, None)
            cid = target.id
        else:
            if not free[weight]:
                errors.append(f"{key}: no free {weight} slots left (the game has 7 small, 9 medium, 8 large extra slots)")
                continue
            cid = free[weight].pop(0)
        if suffix in suffixes and not (replaces and suffix == by_id[cid].suffix):
            errors.append(f"{key}: suffix {suffix!r} is already used by {suffixes[suffix]}")
            continue
        suffixes[suffix] = name
        stats_name = cfg.get("stats_like", replaces)
        if stats_name is None:
            errors.append(f"{key}: set stats_like to a vanilla {weight} character to copy stats from")
            continue
        if stats_name not in VANILLA:
            errors.append(f"{key}: stats_like {stats_name!r} is not a vanilla character")
            continue
        if VANILLA[stats_name][1] != weight:
            errors.append(f"{key}: stats_like {stats_name} is {VANILLA[stats_name][1]}, but this character is {weight}")
            continue
        entry = Entry(cid, key, name, weight, suffix, VANILLA[stats_name][0], True, str(folder))
        by_id[cid] = entry
        customs.append(entry)

    if errors:
        raise RosterError("\n".join(errors))

    roster = list(vanilla.values()) + customs
    lookup = {e.key: e for e in roster}
    lookup.update({e.name: e for e in roster})
    if order:
        ordered, seen = [], set()
        for k in order:
            if k not in lookup:
                errors.append(f"roster.toml: order lists {k!r}, which is not a character")
            elif lookup[k].id in seen:
                errors.append(f"roster.toml: {k!r} appears twice in order")
            else:
                seen.add(lookup[k].id)
                ordered.append(lookup[k])
        if errors:
            raise RosterError("\n".join(errors))
        # Anything not listed goes at the end, so a new character always shows up.
        ordered += [e for e in roster if e.id not in seen]
        roster = ordered
    else:
        roster.sort(key=lambda e: (e.custom, e.id) if e.custom else (False, _vanilla_order(e.id)))
    assert len(roster) <= MAX_CHARACTERS
    return roster


def _vanilla_order(cid):
    # Vanilla select-screen order, read across the 4-column grid.
    order = [0x00, 0x07, 0x10, 0x0F, 0x0A, 0x11, 0x12, 0x14,
             0x08, 0x0D, 0x0E, 0x05, 0x06, 0x0C, 0x01, 0x04,
             0x0B, 0x02, 0x09, 0x03, 0x13, 0x17, 0x16, 0x15]
    return order.index(cid)


def load_settings():
    if not ROSTER_FILE.exists():
        return {}
    return tomllib.loads(ROSTER_FILE.read_text(encoding="utf-8"))


def load_order():
    return load_settings().get("order")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        roster = resolve(load_characters(), load_order())
    except RosterError as e:
        print("error: " + str(e).replace("\n", "\nerror: "), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([asdict(e) for e in roster], indent=2))
        return 0
    for pos, e in enumerate(roster, 1):
        tag = "custom" if e.custom else "vanilla"
        print(f"{pos:2}. {e.name:20} id 0x{e.id:02X}  {e.weight:6}  {e.suffix:6} {tag}")
    used = sum(e.custom for e in roster)
    print(f"{len(roster)}/{MAX_CHARACTERS} slots used ({used} custom).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
