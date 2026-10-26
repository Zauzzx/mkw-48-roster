"""Write a Dolphin input movie (.dtm) that drives GameCube pad 1, so the test
Dolphin can navigate menus with no window focus or screen control.

Usage: python make_dtm.py <out.dtm> <script>

The script is a comma-separated list of steps, each one input poll count plus
buttons held for that many polls, e.g.  "600:,6:A,114:,6:A,..."
Buttons: A B X Y Z S(tart) U D L R (d-pad up/down/left/right).
"pulse:A:6:120:20" expands to 20 x (6 polls with A, then 114 neutral).
Dolphin plays it with  Dolphin.exe -m <out.dtm> ...  and hands input back to
the (idle) live pad when the movie ends.
"""
import struct
import sys

BITS = {"S": 0, "A": 1, "B": 2, "X": 3, "Y": 4, "Z": 5, "U": 6, "D": 7, "L": 8, "R": 9}
CONNECTED = 1 << 14


def pad(buttons):
    b = CONNECTED
    for c in buttons:
        b |= 1 << BITS[c]
    # u16 bitfield (little-endian bitfields as Dolphin stores them), triggers, sticks centred
    return struct.pack("<HBBBBBB", b, 0, 0, 128, 128, 128, 128)


def expand(script):
    out = []
    for step in filter(None, (s.strip() for s in script.split(","))):
        if step.startswith("pulse:"):
            _, btn, on, period, count = step.split(":")
            for _ in range(int(count)):
                out += [pad(btn)] * int(on) + [pad("")] * (int(period) - int(on))
        else:
            n, btn = step.split(":")
            out += [pad(btn)] * int(n)
    return out


def header(inputs, game_id=b"RMCE01"):
    h = bytearray(256)
    h[0:4] = b"DTM\x1a"
    h[4:10] = game_id
    h[10] = 1          # Wii
    h[11] = 0x01       # GameCube pad in port 1, no Wii Remotes
    h[12] = 0          # not from a savestate
    struct.pack_into("<QQQ", h, 13, 0, inputs, 0)   # frame count unknown, input count, lag
    h[49:49 + 7] = b"harness"
    h[137] = 0         # don't override the emulator config
    return bytes(h)


def main():
    out, script = sys.argv[1], sys.argv[2]
    inputs = expand(script)
    with open(out, "wb") as f:
        f.write(header(len(inputs)))
        f.write(b"".join(inputs))
    print(f"{len(inputs)} inputs")


if __name__ == "__main__":
    main()
