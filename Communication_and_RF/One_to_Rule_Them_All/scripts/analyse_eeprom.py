#!/usr/bin/env python3
#
# analyse_eeprom.py
#
# Reverse-engineering helper for ArduPilot AP_Param EEPROM.
#
# Usage:
#     python3 analyse_eeprom.py eeprom.bin
#

import sys
import struct
import math

SIGNING_MAGIC = 0x3852FCD1

# -------------------------------------------------------------

def entropy(buf):
    if not buf:
        return 0.0

    cnt = [0] * 256
    for b in buf:
        cnt[b] += 1

    e = 0.0
    n = len(buf)

    for c in cnt:
        if c:
            p = c / n
            e -= p * math.log2(p)

    return e


# -------------------------------------------------------------

def find_nonzero_regions(data):

    regions = []

    inside = False
    start = 0

    for i, b in enumerate(data):

        if b != 0 and not inside:
            inside = True
            start = i

        elif b == 0 and inside:
            inside = False
            regions.append((start, i))

    if inside:
        regions.append((start, len(data)))

    return regions


# -------------------------------------------------------------

def hexdump(buf, base=0):

    for off in range(0, len(buf), 16):

        line = buf[off:off+16]

        h = " ".join(f"{x:02X}" for x in line)

        a = "".join(chr(x) if 32 <= x < 127 else "." for x in line)

        print(f"{base+off:08X}  {h:<47} {a}")


# -------------------------------------------------------------

def scan_magic(data):

    needle = struct.pack("<I", SIGNING_MAGIC)

    off = 0

    hits = []

    while True:

        p = data.find(needle, off)

        if p < 0:
            break

        hits.append(p)

        off = p + 1

    return hits


# -------------------------------------------------------------

def analyse_signing(data, off):

    blk = data[off:off+48]

    if len(blk) < 48:
        return

    magic, pad = struct.unpack("<II", blk[:8])

    ts = struct.unpack("<Q", blk[8:16])[0]

    key = blk[16:48]

    print()

    print("=" * 60)
    print("Possible SigningKey")
    print("=" * 60)

    print(f"Offset     : 0x{off:04X}")
    print(f"Magic      : 0x{magic:08X}")
    print(f"Pad        : 0x{pad:08X}")
    print(f"Timestamp  : {ts}")
    print(f"Entropy    : {entropy(key):.3f} bits/byte")
    print(f"Key        : {key.hex()}")

    print()

    hexdump(blk, off)


# -------------------------------------------------------------

def main():

    if len(sys.argv) != 2:
        print("usage:")
        print("    python3 analyse_eeprom.py eeprom.bin")
        return

    data = open(sys.argv[1], "rb").read()

    print()

    print("ArduPilot EEPROM Analysis")
    print("-------------------------")

    print()

    print(f"Size : {len(data)} bytes")

    if data[:2] == b"PA":
        print("Magic: PA")
    else:
        print("Magic: unknown")

    if len(data) >= 4:
        print(f"Revision byte : {data[2]}")

    print()

    print("Non-zero regions")

    print("----------------")

    regs = find_nonzero_regions(data)

    for s, e in regs:

        ent = entropy(data[s:e])

        print(f"0x{s:04X} - 0x{e-1:04X}   "
              f"{e-s:5d} bytes   entropy={ent:.2f}")

    print()

    print("Searching for SigningKey magic...")

    hits = scan_magic(data)

    if not hits:
        print("No magic found.")
        return

    print()

    for h in hits:
        analyse_signing(data, h)


if __name__ == "__main__":
    main()
