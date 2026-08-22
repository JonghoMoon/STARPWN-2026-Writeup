#!/usr/bin/env python3

import os
import time
from collections import Counter

# Its scanner for MAVLink.

os.environ["MAVLINK20"] = "1"

from pymavlink import mavutil

HOST = "0.cloud.chals.io"
PORT = 15174
KEY = bytes.fromhex("d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126")

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

print("[*] Connected")
print("[*] Collecting telemetry for 5 seconds...\n")

counter = Counter()
systems = set()

t0 = time.time()

while time.time() - t0 < 5:

    msg = m.recv_match(blocking=True, timeout=1)

    if msg is None:
        continue

    counter[msg.get_type()] += 1
    systems.add(msg.get_srcSystem())

print("=== Systems Seen ===")
print(sorted(systems))

print("\n=== Message Types ===")
for k, v in counter.items():
    print(f"{k:30} {v}")
