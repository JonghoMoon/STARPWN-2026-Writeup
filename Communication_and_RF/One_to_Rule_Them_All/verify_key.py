#!/usr/bin/env python3

import hashlib
import socket
import struct
import sys
import time


# ---------------------------------------------------------

def recv_one_signed_frame(host, port, timeout=10):

    s = socket.create_connection((host, port), timeout=10)

    s.settimeout(5)

    buf = b""

    t0 = time.time()

    while time.time() - t0 < timeout:

        try:
            d = s.recv(4096)

        except socket.timeout:
            continue

        if not d:
            break

        buf += d

        #
        # scan MAVLink2 frames
        #

        i = 0

        while i + 12 < len(buf):

            if buf[i] != 0xFD:
                i += 1
                continue

            payload_len = buf[i + 1]

            incompat = buf[i + 2]

            signed = incompat & 0x01

            total = 10 + payload_len + 2

            if signed:
                total += 13

            if i + total > len(buf):
                break

            frame = buf[i:i + total]

            if signed:
                s.close()
                return frame

            i += total

    s.close()

    raise RuntimeError("No signed MAVLink2 frame received")


# ---------------------------------------------------------

def decode_frame(frame):

    payload_len = frame[1]

    incompat = frame[2]

    compat = frame[3]

    seq = frame[4]

    sysid = frame[5]

    compid = frame[6]

    msgid = frame[7] | (frame[8] << 8) | (frame[9] << 16)

    crc_off = 10 + payload_len

    crc = struct.unpack("<H", frame[crc_off:crc_off + 2])[0]

    sig = frame[crc_off + 2:]

    link_id = sig[0]

    timestamp = int.from_bytes(sig[1:7], "little")

    signature = sig[7:13]

    return {

        "payload_len": payload_len,

        "seq": seq,

        "sysid": sysid,

        "compid": compid,

        "msgid": msgid,

        "crc": crc,

        "link_id": link_id,

        "timestamp": timestamp,

        "signature": signature,

        "frame_without_signature": frame[:crc_off + 2],

    }


# ---------------------------------------------------------

def verify(info, key):

    h = hashlib.sha256()

    h.update(key)

    h.update(info["frame_without_signature"])

    h.update(bytes([info["link_id"]]))

    h.update(info["timestamp"].to_bytes(6, "little"))

    calc = h.digest()[:6]

    return calc


# ---------------------------------------------------------

def main():

    if len(sys.argv) != 4:

        print()

        print("usage")

        print()

        print("python3 verify_key.py HOST PORT KEYHEX")

        print()

        return

    host = sys.argv[1]

    port = int(sys.argv[2])

    key = bytes.fromhex(sys.argv[3])

    frame = recv_one_signed_frame(host, port)

    info = decode_frame(frame)

    calc = verify(info, key)

    print()

    print("=" * 60)

    print("MAVLink2 Signed Packet")

    print("=" * 60)

    print(f"Payload Length : {info['payload_len']}")

    print(f"Sequence       : {info['seq']}")

    print(f"System ID      : {info['sysid']}")

    print(f"Component ID   : {info['compid']}")

    print(f"Message ID     : {info['msgid']}")

    print(f"CRC            : 0x{info['crc']:04X}")

    print()

    print(f"Link ID        : {info['link_id']}")

    print(f"Timestamp      : {info['timestamp']}")

    print()

    print(f"Received Sig   : {info['signature'].hex()}")

    print(f"Computed Sig   : {calc.hex()}")

    print()

    if calc == info["signature"]:

        print("[+] KEY VERIFIED")

    else:

        print("[-] WRONG KEY")

    print()

    print("=" * 60)


if __name__ == "__main__":
    main()
