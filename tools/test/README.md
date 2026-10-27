# Test harness (Dolphin, no Riivolution GUI)

- `make_testdisc.py` writes a Riivolution XML's `<memory>` patches into an
  extracted disc's `sys/main.dol` (same effect as Riivolution) and overlays
  `--overlay <dir>` folders (each holding `files/`) onto the disc's `files/`,
  restoring the originals between runs.
- `make_dtm.py` writes a Dolphin input movie for GameCube pad 1 (button
  pulses), so menus can be driven with no window focus.
- `contact_sheet.py` tiles every n-th dumped frame into one labelled image
  (needs Pillow), to see where a run went.

Typical run, with a disc extracted by `wit extract <game> <disc> --psel data`:

    python tools/test/make_testdisc.py out/riivolution/mkw-48-roster.xml out <disc>/../main.dol.orig <disc>/sys/main.dol --overlay out/mkw-48-roster --overlay ui-out
    python tools/test/make_dtm.py nav.dtm "pulse:A:6:300:14,3000:,pulse:A:6:900:2,30000:"
    Dolphin.exe -u <separate user folder> -b -e <disc>/sys/main.dol -m nav.dtm

Use a separate Dolphin user folder (`-u`) with OSREPORT logging to file,
GameCube pad in port 1, and frame dumping as images to check the screens.
In that folder's config:

- `Dolphin.ini` `[Core] CPUThread = False`: dual core makes playback timing
  vary from run to run.
- `Dolphin.ini` `[Interface] UsePanicHandlers = False`: a movie boots with a
  region warning dialog that otherwise waits for a click.
- `GCPadNew.ini` with no `Device`, `WiimoteNew.ini` with `Source = 0` for all
  Wii Remotes: keyboard and mouse input otherwise reaches the game whenever
  the window has focus, and once the movie ends.

With that, a movie replays the same way every run. The script above (USA
disc, a save whose license needs creating) stops on the Grand Prix
character screen; the game reads the pad about twice a frame, and presses
during a screen load are lost, hence the pause before the last two.

No game files belong in the repository.
