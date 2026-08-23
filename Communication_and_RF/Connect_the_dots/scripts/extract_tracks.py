#!/usr/bin/env python3

import sys
import struct
import math
from collections import defaultdict

import matplotlib.pyplot as plt

MAVLINK2_MAGIC = 0xFD
HDR_LEN = 10
CRC_LEN = 2
SIGN_LEN = 13

MSG_GLOBAL_POSITION_INT = 33


def parse_positions(path):

    positions = defaultdict(list)

    with open(path, "rb") as f:

        leftover = b""

        while True:

            chunk = f.read(5_000_000)

            if not chunk:
                break

            data = leftover + chunk

            i = 0
            last_safe = 0

            while i < len(data) - HDR_LEN:

                if data[i] != MAVLINK2_MAGIC:
                    i += 1
                    continue

                plen = data[i + 1]
                incompat = data[i + 2]

                sysid = data[i + 5]

                msgid = (
                    data[i + 7]
                    | (data[i + 8] << 8)
                    | (data[i + 9] << 16)
                )

                frame_len = (
                    HDR_LEN
                    + plen
                    + CRC_LEN
                    + (SIGN_LEN if incompat & 0x01 else 0)
                )

                if i + frame_len > len(data):
                    break

                if msgid == MSG_GLOBAL_POSITION_INT:

                    payload = data[i + HDR_LEN:i + HDR_LEN + plen]

                    payload += b"\x00" * (28 - len(payload))

                    (
                        _,
                        lat,
                        lon,
                        alt,
                        _,
                        _,
                        _,
                        _,
                        _
                    ) = struct.unpack("<IiiiihhhH", payload[:28])

                    positions[sysid].append(
                        (
                            lat / 1e7,
                            lon / 1e7,
                            alt / 1000.0,
                        )
                    )

                last_safe = i
                i += frame_len

            leftover = data[last_safe:]

    return positions


def save_tracks(positions):

    for sysid, pts in sorted(positions.items()):

        if len(pts) < 2:
            continue

        lat = [p[0] for p in pts]
        lon = [p[1] for p in pts]

        plt.figure(figsize=(7, 7))

        plt.plot(lon, lat, linewidth=1)

        plt.scatter(
            lon[0],
            lat[0],
            marker="o",
            s=60,
            label="Start"
        )

        plt.scatter(
            lon[-1],
            lat[-1],
            marker="x",
            s=80,
            label="End"
        )

        plt.axis("equal")
        plt.grid(True)
        plt.legend()

        plt.title(f"Drone SYSID {sysid}")

        plt.xlabel("Longitude")
        plt.ylabel("Latitude")

        outfile = f"drone_{sysid:03d}.png"

        plt.savefig(outfile, dpi=250, bbox_inches="tight")

        plt.close()

        print(outfile)


def main():

    if len(sys.argv) < 2:
        print("Usage:")
        print("python3 extract_tracks.py PRISM_S03_B10-30_20260830.raw")
        return

    positions = parse_positions(sys.argv[1])

    print()

    print("Detected drones:")

    for k in sorted(positions):
        print(f"SYSID {k}: {len(positions[k])} points")

    print()

    save_tracks(positions)


if __name__ == "__main__":
    main()
