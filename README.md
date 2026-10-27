# MKW 48 Roster

A Mario Kart Wii mod (Dolphin / Riivolution, USA RMCE01 first) that raises the
roster to **48 characters** and lays the character select screen out as
horizontal rows along the bottom, with the driver previews across the top.

**Status:** works in Dolphin. A custom character can be picked from the
48-button screen, races with its own kart and driver, and shows its icon on the
minimap and results screen. `unlock_all` opens every character, kart, cup,
150cc and Mirror. 1- and 2-player select screens are checked; 4-player isn't yet.

## How 48 works

The game already has 48 internal character IDs: the 24 drivers, 21 Mii IDs, and
3 menu-preview IDs for Peach, Daisy and Rosalina. None of those 24 extra
IDs gets its own button. Its file-name and display tables are sized for all 48; stats are copied
from a vanilla character (`stats_like`). This mod turns
those 24 hidden IDs into real roster slots. The Mii button is removed to make
room. Each extra ID has a fixed weight class, so the free slots are
**7 small, 9 medium, 8 large**.

## Setup (once)

1. Install [Python 3.11+](https://www.python.org/downloads/) and
   [Wiimm's SZS Tools](https://szs.wiimm.de) (`wszst`, `wbmgt`, `wimgt` on
   your PATH).
2. Extract your own USA disc with Wiimm's ISO Tools:
   `wit extract MarioKartWii.iso mkw/`. The folder you need below is
   `mkw/DATA/files` (it holds `Race/` and `Scene/`).

## Adding a character

You can add up to 24 new characters on top of the 24 vanilla ones, for 48 in
total. Each new character takes a free slot of its weight class: 7 small,
9 medium and 8 large. Adding one never needs a compiler.

1. **Copy the template.** Copy `characters/_example/` to
   `characters/shadow/` (any folder name without a leading `_`).
2. **Fill in `character.toml`:**
   ```toml
   name = "Shadow"          # shown in menus (max 20 characters)
   weight = "medium"        # small, medium or large
   suffix = "sh"            # 2-6 lowercase letters/digits, used in file names
   stats_like = "Mario"     # vanilla character of the same weight to copy stats from
   # replaces = "Waluigi"   # optional: take over a vanilla slot instead of a free one
   # clone_from = "Mario"   # optional: borrow this character's files for anything missing
   ```
3. **Add its files** to the folder. Anything you leave out is borrowed from
   `clone_from`, so you can start with just `character.toml` and a
   `clone_from` line and add real models later.
   ```
   characters/shadow/
     character.toml
     icon.png            64x64 select-screen icon (also used on the race minimap)
     menu/model.brres    3D model shown in the select-screen preview
     kart/<kart>.szs     one per vehicle, named like the game's file without the
                         character suffix: Race/Kart/st_kart-mr.szs -> st_kart.szs
   ```
4. **Check it:** `python3 tools/roster.py` lists every character, its slot and
   its weight, and explains any mistake (a taken suffix, no free slot, and so on).
5. **Build:**
   ```
   python3 tools/build.py
   python3 tools/pack_ui.py --game mkw/DATA/files --out out/mkw-48-roster
   python3 tools/pack_assets.py --game mkw/DATA/files --out out/mkw-48-roster
   ```
6. **Play:** copy everything inside `out/` into Dolphin's `Load/Riivolution`
   folder (or the root of your SD card on a Wii). In Dolphin, right-click the
   game, choose "Start with Riivolution Patches", and turn on "48 Roster".

To remove a character, delete its folder or add `enabled = false` to its
`character.toml`, then build again.

## Settings in `roster.toml`

- `order`: the button order, left to right and top row first, using folder
  names or vanilla names. Characters you don't list are added at the end, so a
  new character always shows up.
- `unlock_all` (default `true`): play as if your save were 100% complete. The
  unlocks are not written into your save file; set it to `false` to keep the
  normal unlock rules.

## For developers

The game code patch is prebuilt in `prebuilt/` and reads the roster from
`roster48.bin` at boot. Only changes to `payload/` need
`tools/compile_payload.py` (clang and ld.lld with the PowerPC target).
`tools/test/` holds the Dolphin test harness. Run the unit tests with
`python3 -m unittest discover tests`.

## Repository layout

- `characters/`: one folder per custom character.
- `tools/ids.py`: the 48 IDs and their weight classes.
- `tools/roster.py`: assigns IDs and button order, validates.
- `tools/layout.py`: select-screen geometry (rows at the bottom, previews on top).
- `payload/`: the C code patch, built with clang for PowerPC (no CodeWarrior);
  `prebuilt/` holds the compiled result.
- `addresses/`: per-region game addresses found by reverse engineering.

No Nintendo files are in this repository. You need your own disc.
