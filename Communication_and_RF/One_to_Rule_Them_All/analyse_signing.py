#!/usr/bin/env python3

import re
import struct
import sys

# ---------------------------------------------------------

def parse_gcs_signing(path):

    src = open(path, encoding="utf8").read()

    #
    # SIGNING_KEY_MAGIC
    #

    m = re.search(
        r'#define\s+SIGNING_KEY_MAGIC\s+(0x[0-9A-Fa-f]+)',
        src
    )

    if not m:
        raise RuntimeError("SIGNING_KEY_MAGIC not found")

    magic = int(m.group(1), 16)

    #
    # secret_key size
    #

    m = re.search(
        r'secret_key\s*\[\s*(\d+)\s*\]',
        src
    )

    if not m:
        raise RuntimeError("secret_key[] not found")

    key_len = int(m.group(1))

    #
    # struct size
    #
    # uint32
    # uint64 (8-byte aligned)
    # uint8[key]
    #

    off = 0

    #
    # uint32 magic
    #

    off += 4

    #
    # uint64 timestamp
    #

    off = (off + 7) & ~7

    ts_off = off

    off += 8

    key_off = off

    off += key_len

    struct_size = off

    return {

        "magic": magic,

        "key_len": key_len,

        "struct_size": struct_size,

        "timestamp_offset": ts_off,

        "key_offset": key_off,
    }


# ---------------------------------------------------------

def scan(data, info):

    needle = struct.pack("<I", info["magic"])

    off = 0

    while True:

        p = data.find(needle, off)

        if p < 0:
            break

        yield p

        off = p + 1


# ---------------------------------------------------------

def dump_candidate(data, off, info):

    blk = data[off:off + info["struct_size"]]

    magic = struct.unpack("<I", blk[:4])[0]

    ts = struct.unpack(
        "<Q",
        blk[
            info["timestamp_offset"]:
            info["timestamp_offset"] + 8
        ]
    )[0]

    key = blk[
        info["key_offset"]:
        info["key_offset"] + info["key_len"]
    ]

    print("=" * 60)

    print(f"Offset     : 0x{off:04X}")

    print(f"Magic      : 0x{magic:08X}")

    print(f"Timestamp  : {ts}")

    print(f"Key        : {key.hex()}")

    print()

    return key


# ---------------------------------------------------------

def main():

    if len(sys.argv) != 3:

        print()

        print("usage")

        print()

        print("python3 analyse_signing.py eeprom.bin GCS_Signing.cpp")

        print()

        return

    eeprom = open(sys.argv[1], "rb").read()

    info = parse_gcs_signing(sys.argv[2])

    print()

    print("Signing structure")

    print("-----------------")

    print(f"MAGIC        : 0x{info['magic']:08X}")

    print(f"Struct Size  : {info['struct_size']}")

    print(f"Key Length   : {info['key_len']}")

    print()

    found = False

    for p in scan(eeprom, info):

        found = True

        dump_candidate(eeprom, p, info)

    if not found:

        print("No SigningKey structure found.")


if __name__ == "__main__":
    main()
