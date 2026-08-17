#!/usr/bin/env python3

import os
import sys
import time

# 반드시 import보다 먼저
os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil


def main():

    if len(sys.argv) != 4:
        print()
        print("usage")
        print("python3 heartbeat.py HOST PORT KEYHEX")
        print()
        return

    host = sys.argv[1]
    port = int(sys.argv[2])
    key = bytes.fromhex(sys.argv[3])

    print(f"[*] Connecting to tcp:{host}:{port}")

    m = mavutil.mavlink_connection(
        f"tcp:{host}:{port}",
        dialect="ardupilotmega",
        source_system=255,
        source_component=190
    )

    print("[*] Installing signing key")

    m.setup_signing(
        key,
        sign_outgoing=True,
        allow_unsigned_callback=lambda mav, msgid: True
    )

    print("[*] Waiting for incoming telemetry...")

    t0 = time.time()

    while time.time() - t0 < 3:

        msg = m.recv_match(blocking=True, timeout=1)

        if msg:
            print(
                f"RX: sys={msg.get_srcSystem():3d} "
                f"comp={msg.get_srcComponent():3d} "
                f"{msg.get_type()}"
            )

    print()

    print("[*] Sending HEARTBEAT")

    m.mav.heartbeat_send(

        mavutil.mavlink.MAV_TYPE_GCS,

        mavutil.mavlink.MAV_AUTOPILOT_INVALID,

        0,

        0,

        0

    )

    print("[+] HEARTBEAT transmitted")

    print()

    print("[*] Waiting for replies...")

    t0 = time.time()

    while time.time() - t0 < 10:

        msg = m.recv_match(blocking=True, timeout=1)

        if not msg:
            continue

        print(
            f"RX: sys={msg.get_srcSystem():3d} "
            f"comp={msg.get_srcComponent():3d} "
            f"{msg.get_type()}"
        )


if __name__ == "__main__":
    main()
