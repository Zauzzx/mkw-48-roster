"""Read and write the placement records of MKW UI control files (.brctr).

A BRCTR ("bctr") file says which layout a control uses, which animations it
plays, and where each named variant of the control sits on screen. This
module only touches the variant (placement) records; the animation section is
copied through unchanged.

File layout (all big-endian):
  0x00  "bctr", u16 version (2), u16 ?
  0x08  u16 layout dir name, u16 layout name (string pool offsets)
  0x0C  u16 offset of the animation section
  0x0E  u16 offset of the variant section
  0x10  u16 offset of the string pool, u16 ?
  variant section:
    u16 offset of the first record (from the section start), u16 record count,
    2 x (u16 offset, u16 count) of two tables stored after the records
        (offsets from the section start; the first holds 8-byte message
        entries, the second is usually empty)
    records, 0x3C bytes each:
      u16 name, u8 0, u8 alpha, u16 1, u16 0, f32 unknown,
      f32 x, y, z, scale x, scale y   (4:3)
      f32 x, y, z, scale x, scale y   (16:9)
      8 bytes (usually 0; kept as read)
  string pool: NUL-terminated strings; every name is an offset into it.

  python3 tools/brctr.py <file.brctr>    list the records
"""

import struct
import sys
from dataclasses import dataclass, field

RECORD_SIZE = 0x3C


@dataclass
class Placement:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


@dataclass
class Record:
    name: str
    alpha: int = 255
    unknown: float = 0.0
    wide4_3: Placement = field(default_factory=Placement)
    wide16_9: Placement = field(default_factory=Placement)
    flags: bytes = b"\x00\x01\x00\x00"
    extra: bytes = bytes(8)


class Brctr:
    def __init__(self, data):
        if data[:4] != b"bctr":
            raise ValueError("not a BRCTR file")
        self.head = bytearray(data[:0x14])
        self.var_off = struct.unpack_from(">H", data, 0x0E)[0]
        self.pool_off = struct.unpack_from(">H", data, 0x10)[0]
        self.anim = bytes(data[0x14:self.var_off])  # copied through unchanged
        first, count = struct.unpack_from(">HH", data, self.var_off)
        self.var_head_extra = bytes(data[self.var_off + 4:self.var_off + first])
        # data after the records (message tables), copied through and re-pointed
        self.tail = bytes(data[self.var_off + first + count * RECORD_SIZE:self.pool_off])
        self.old_end = first + count * RECORD_SIZE
        self.pool = bytearray(data[self.pool_off:])
        self.records = []
        for i in range(count):
            o = self.var_off + first + i * RECORD_SIZE
            name_off, zero, alpha = struct.unpack_from(">HBB", data, o)
            vals = struct.unpack_from(">11f", data, o + 8)
            self.records.append(Record(
                name=self._string(name_off), alpha=alpha, unknown=vals[0],
                wide4_3=Placement(*vals[1:6]), wide16_9=Placement(*vals[6:11]),
                flags=bytes(data[o + 4:o + 8]), extra=bytes(data[o + 0x34:o + RECORD_SIZE])))

    def _string(self, off):
        end = self.pool.index(0, off)
        return self.pool[off:end].decode("ascii")

    def _intern(self, s):
        """Offset of `s` in the string pool, appending it if needed. Existing
        offsets never move, so the animation section stays valid."""
        b = s.encode("ascii") + b"\0"
        i = 0
        while True:
            i = self.pool.find(b, i)
            if i < 0:
                break
            if i == 0 or self.pool[i - 1] == 0:
                return i
            i += 1
        off = len(self.pool)
        self.pool += b
        return off

    def get(self, name):
        for r in self.records:
            if r.name == name:
                return r
        return None

    def set(self, record):
        """Replace the record with the same name, or append it."""
        for i, r in enumerate(self.records):
            if r.name == record.name:
                self.records[i] = record
                return
        self.records.append(record)

    def to_bytes(self):
        names = [self._intern(r.name) for r in self.records]
        first = 4 + len(self.var_head_extra)
        end = first + len(self.records) * RECORD_SIZE
        extra = bytearray(self.var_head_extra)
        # the two (offset, count) table pointers move with the end of the records
        for at in (0, 4):
            if len(extra) >= at + 4:
                old = struct.unpack_from(">H", extra, at)[0]
                struct.pack_into(">H", extra, at, old + end - self.old_end)
        sec = bytearray(struct.pack(">HH", first, len(self.records)) + extra)
        for r, n in zip(self.records, names):
            p, w = r.wide4_3, r.wide16_9
            sec += struct.pack(">HBB", n, 0, r.alpha) + r.flags
            sec += struct.pack(">11f", r.unknown, p.x, p.y, p.z, p.scale_x, p.scale_y,
                               w.x, w.y, w.z, w.scale_x, w.scale_y)
            sec += r.extra
        sec += self.tail
        head = bytearray(self.head)
        pool_off = self.var_off + len(sec)
        struct.pack_into(">H", head, 0x10, pool_off)
        return bytes(head) + self.anim + bytes(sec) + bytes(self.pool)


def load(path):
    with open(path, "rb") as f:
        return Brctr(f.read())


def save(ctr, path):
    with open(path, "wb") as f:
        f.write(ctr.to_bytes())


def main(argv):
    for path in argv:
        ctr = load(path)
        print(path)
        for r in ctr.records:
            a, b = r.wide4_3, r.wide16_9
            print(f"  {r.name:<28} 4:3 ({a.x:g},{a.y:g}) x{a.scale_x:g}   16:9 ({b.x:g},{b.y:g}) x{b.scale_x:g}")


if __name__ == "__main__":
    main(sys.argv[1:])
