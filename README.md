# MKW 48 Roster

A Mario Kart Wii mod (Dolphin / Riivolution, USA RMCE01 first) that raises the
roster to **48 characters** and lays the character select screen out as
horizontal rows along the bottom, with the driver previews across the top.

**Status: in development.** The loader and character-ID patches run in
Dolphin; the 48-button select screen is written and being tested.

## How 48 works

The game already has 48 internal character IDs: the 24 drivers, 21 Mii IDs, and
3 menu-preview IDs for Peach, Daisy and Rosalina. None of those 24 extra
IDs gets its own button. Its file-name and display tables are sized for all 48; stats are copied
from a vanilla character (`stats_like`). This mod turns
those 24 hidden IDs into real roster slots. The Mii button is removed to make
room. Each extra ID has a fixed weight class, so the free slots are
**7 small, 9 medium, 8 large**.

## Adding a character

1. Make a folder `characters/<name>/` with a `character.toml`:
   ```toml
   name = "Shadow"          # shown in menus (max 20 characters)
   weight = "medium"        # small, medium or large
   suffix = "sh"            # used in file names, e.g. st_kart-sh.szs
   stats_like = "Mario"     # vanilla character to copy stats from
   # replaces = "Waluigi"   # optional: take over a vanilla slot instead
   ```
2. Put its files in the folder:
   ```
   characters/shadow/
     character.toml
     icon.png            64x64 select-screen icon
     menu/model.brres    3D model shown on the select screen
     kart/<kart>.szs     one per vehicle, named like the game's file without
                         the character suffix (Race/Kart/st_kart-mr.szs -> st_kart.szs)
   ```
   Missing files are filled from `clone_from` if set, which is handy for a
   placeholder while you work on the models.
3. Run `python3 tools/roster.py` to check it and see where it landed.

Button order is set by `order` in `roster.toml`; anything not listed is added
at the end, so a new character always shows up.

## Repository layout

- `characters/`: one folder per custom character.
- `tools/ids.py`: the 48 IDs and their weight classes.
- `tools/roster.py`: assigns IDs and button order, validates.
- `tools/layout.py`: select-screen geometry (rows at the bottom, previews on top).
- `payload/`: the C code patch, built with clang for PowerPC (no CodeWarrior).
- `addresses/`: per-region game addresses found by reverse engineering.

No Nintendo files are in this repository. You need your own disc.
