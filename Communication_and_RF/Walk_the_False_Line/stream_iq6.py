#!/usr/bin/env python3
"""
Real-time TCP streamer for SPWN1 GPS L1 C/A complex baseband input.

Input IQ format:
  - signed 16-bit little-endian I/Q
  - interleaved: I0,Q0,I1,Q1,...
  - 4 bytes per complex sample

Protocol:
  Before the first IQ sample, send exactly:
    SPWN1 scenario_t=YYYY/MM/DD,HH:MM:SS sample_rate=<sample_rate>\n

Usage:
  python3 stream_iq6.py <iq_file> <host> <port> <scenario_t> [sample_rate] [chunk_ms]

Example:
  python3 stream_iq6.py gpssim.bin 0.cloud.chals.io 31211 \
      2026/05/10,12:16:35 2600000 10
"""

import os
import re
import socket
import sys
import time


BYTES_PER_COMPLEX_SAMPLE = 4


def die(msg):
    raise SystemExit(msg)


if len(sys.argv) < 5:
    print(__doc__.strip())
    raise SystemExit(2)

path = sys.argv[1]
host = sys.argv[2]
port = int(sys.argv[3])
scenario_t = sys.argv[4]
sample_rate = int(sys.argv[5]) if len(sys.argv) > 5 else 2_600_000
chunk_ms = float(sys.argv[6]) if len(sys.argv) > 6 else 10.0

if not re.fullmatch(r"\d{4}/\d{2}/\d{2},\d{2}:\d{2}:\d{2}", scenario_t):
    die("scenario_t must be exactly YYYY/MM/DD,HH:MM:SS")

if sample_rate <= 0:
    die("sample_rate must be > 0")

if chunk_ms <= 0:
    die("chunk_ms must be > 0")

if not os.path.isfile(path):
    die(f"IQ file not found: {path}")

file_size = os.path.getsize(path)

if file_size == 0:
    die("IQ file is empty")

if file_size % BYTES_PER_COMPLEX_SAMPLE:
    die(
        f"IQ file size ({file_size} bytes) is not divisible by 4; "
        "expected signed int16-le interleaved I/Q."
    )

num_samples = file_size // BYTES_PER_COMPLEX_SAMPLE
byte_rate = sample_rate * BYTES_PER_COMPLEX_SAMPLE
duration_s = num_samples / sample_rate

# Chunk must contain complete I/Q sample pairs.
chunk_size = int(round(byte_rate * chunk_ms / 1000.0))
chunk_size = max(BYTES_PER_COMPLEX_SAMPLE, chunk_size)
chunk_size -= chunk_size % BYTES_PER_COMPLEX_SAMPLE

header = (
    f"SPWN1 scenario_t={scenario_t} sample_rate={sample_rate}\n"
).encode("ascii")

print(f"[*] File        : {path}")
print(f"[*] Size        : {file_size:,} bytes")
print("[*] Format      : signed int16 little-endian I/Q, interleaved")
print(f"[*] Samples     : {num_samples:,} complex samples")
print(f"[*] Sample rate : {sample_rate:,} complex samples/s")
print(f"[*] Byte rate   : {byte_rate:,} B/s ({byte_rate * 8 / 1e6:.3f} Mbit/s)")
print(f"[*] Duration    : {duration_s:.6f} s")
print(f"[*] Chunk       : {chunk_size:,} bytes ~= {1000 * chunk_size / byte_rate:.3f} ms")
print(f"[*] Header      : {header.decode('ascii').rstrip()}")
print(f"[*] Connecting to {host}:{port} ...")

# Use timeout only for connect().
s = socket.create_connection((host, port), timeout=10)

# After connection, use ordinary blocking I/O.
s.settimeout(None)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

try:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
except OSError:
    pass

try:
    actual_sndbuf = s.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
except OSError:
    actual_sndbuf = -1

print(f"[*] Connected. SO_SNDBUF={actual_sndbuf:,} bytes")

try:
    s.sendall(header)
except OSError as e:
    s.close()
    die(f"[!] Failed while sending SPWN1 header: {e!r}")

print("[*] Header sent. Streaming IQ in real time...")

t0 = time.perf_counter()
sent = 0
next_report = 1.0
worst_send_block = 0.0

try:
    with open(path, "rb", buffering=0) as f:
        while sent < file_size:
            # Target wall-clock time for the START of this chunk.
            target_start = sent / byte_rate

            # Coarse sleep, then yield until target.
            while True:
                now_rel = time.perf_counter() - t0
                remaining = target_start - now_rel

                if remaining <= 0:
                    break

                if remaining > 0.002:
                    time.sleep(remaining - 0.001)
                else:
                    time.sleep(0)

            to_read = min(chunk_size, file_size - sent)
            chunk = f.read(to_read)

            if not chunk:
                raise RuntimeError("unexpected EOF while streaming IQ file")

            send_start = time.perf_counter()

            try:
                s.sendall(chunk)
            except (ConnectionResetError, BrokenPipeError, TimeoutError, OSError) as e:
                wall_t = time.perf_counter() - t0
                sim_t = sent / byte_rate

                print()
                print("[!] SEND FAILED")
                print(f"    error       = {e!r}")
                print(f"    sent bytes  = {sent:,} / {file_size:,}")
                print(f"    sent pct    = {100.0 * sent / file_size:.6f}%")
                print(f"    sim time    = {sim_t:.6f} s")
                print(f"    wall time   = {wall_t:.6f} s")
                print(f"    lag         = {(wall_t - sim_t) * 1000:+.3f} ms")
                print(f"    chunk size  = {len(chunk):,} bytes")
                print(f"    chunk ms    = {1000.0 * len(chunk) / byte_rate:.6f} ms")
                print(f"    max block   = {worst_send_block * 1000:.3f} ms")
                raise

            send_block = time.perf_counter() - send_start
            worst_send_block = max(worst_send_block, send_block)

            sent += len(chunk)

            sim_t = sent / byte_rate
            wall_t = time.perf_counter() - t0

            if sim_t >= next_report or sent == file_size:
                lag = wall_t - sim_t

                print(
                    f"    sim={sim_t:8.3f}s  "
                    f"{100.0 * sent / file_size:6.2f}%  "
                    f"wall={wall_t:8.3f}s  "
                    f"lag={lag * 1000:+8.2f} ms  "
                    f"max_send_block={worst_send_block * 1000:8.2f} ms"
                )

                while next_report <= sim_t:
                    next_report += 1.0

                worst_send_block = 0.0

except KeyboardInterrupt:
    wall_t = time.perf_counter() - t0
    sim_t = sent / byte_rate
    print()
    print("[!] Interrupted by user")
    print(f"    sent bytes = {sent:,}")
    print(f"    sim time   = {sim_t:.6f} s")
    print(f"    wall time  = {wall_t:.6f} s")
    raise SystemExit(130)

finally:
    try:
        s.shutdown(socket.SHUT_WR)
    except OSError:
        pass

    s.close()

if sent == file_size:
    wall_t = time.perf_counter() - t0
    print("[*] Done.")
    print(f"[*] Final wall time : {wall_t:.6f} s")
    print(f"[*] Final sim time  : {duration_s:.6f} s")
    print(f"[*] Final lag       : {(wall_t - duration_s) * 1000:+.3f} ms")
