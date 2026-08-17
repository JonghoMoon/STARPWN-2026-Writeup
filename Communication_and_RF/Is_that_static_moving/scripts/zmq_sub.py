#!/usr/bin/env python3
import zmq, sys

HOST = "0.cloud.chals.io"
PORT = 32927

ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.connect(f"tcp://{HOST}:{PORT}")
sock.setsockopt(zmq.SUBSCRIBE, b"")

print(f"[*] Connected to tcp://{HOST}:{PORT}", file=sys.stderr)

count = 0
with open("synnode_signal.bin", "wb") as f:
    try:
        while True:
            msg = sock.recv_multipart()
            count += 1
            for i, part in enumerate(msg):
                print(f"[msg {count}] part {i}: len={len(part)} first32={part[:32]!r}", file=sys.stderr)
                f.write(part)
                f.write(b"\n---PART---\n")
            if count % 20 == 0:
                print(f"[*] {count} messages so far...", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"[*] Done. Total: {count}", file=sys.stderr)
