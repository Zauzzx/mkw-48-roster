# Test harness (Dolphin, no Riivolution GUI)

- `make_testdisc.py` writes a Riivolution XML's `<memory>` patches into an
  extracted disc's `sys/main.dol` (same effect as Riivolution) and overlays
  `--overlay <dir>` folders (each holding `files/`) onto the disc's `files/`,
  restoring the originals between runs.
- `make_dtm.py` writes a Dolphin input movie for GameCube pad 1 (button
  pulses), so menus can be driven with no window focus.

Typical run, with a disc extracted by `wit extract <game> <disc> --psel data`:

    python tools/test/make_testdisc.py out/riivolution/mkw-48-roster.xml out <disc>/../main.dol.orig <disc>/sys/main.dol --overlay out/mkw-48-roster --overlay ui-out
    python tools/test/make_dtm.py nav.dtm "900:,pulse:A:8:400:80"
    Dolphin.exe -u <separate user folder> -b -e <disc>/sys/main.dol -m nav.dtm

Use a separate Dolphin user folder (`-u`) with OSREPORT logging to file,
GameCube pad in port 1, and frame dumping as images to check the screens.
No game files belong in the repository.
