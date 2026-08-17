#!/usr/bin/env python3

import os
import struct
import time

os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil

HOST = "0.cloud.chals.io"
PORT = 33247

KEY = bytes.fromhex(
    "d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126"
)

TARGET_SYS = 1
TARGET_COMP = 1

OP_LIST = 3


def make_list_packet(path, seq=0):
    hdr = struct.pack(
        "<HBBBBBBI",
        seq,            # seq
        0,              # session
        OP_LIST,
        len(path),
        0,              # req opcode
        0,
        0,
        0               # offset
    )

    return (hdr + path.encode()).ljust(251, b"\x00")


def parse_entries(data):

    for e in data.split(b"\x00"):
        if not e:
            continue

        kind = chr(e[0])
        name = e[1:].decode(errors="ignore")

        if kind == "D":
            print("[DIR ]", name)

        elif kind == "F":
            print("[FILE]", name)

        else:
            print("[ ? ]", e)


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

# heartbeat
m.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0,
    0,
    0,
)

time.sleep(0.5)

path = "DCIM"

print(f"[*] LIST {path}")

payload = make_list_packet(path)

m.mav.file_transfer_protocol_send(
    0,
    TARGET_SYS,
    TARGET_COMP,
    payload
)

while True:

    msg = m.recv_match(blocking=True, timeout=5)

    if msg is None:
        print("Timeout")
        break

    if msg.get_type() != "FILE_TRANSFER_PROTOCOL":
        continue

    raw = bytes(msg.payload)

    seq, session, opcode, size, req, burst, pad, offset = struct.unpack(
        "<HBBBBBBI",
        raw[:12]
    )

    print()
    print("opcode :", opcode)
    print("size   :", size)
    print("offset :", offset)

    parse_entries(raw[12:12+size])

    break
