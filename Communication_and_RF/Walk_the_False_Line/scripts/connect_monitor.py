#!/usr/bin/env python3

import socket
import time

HOST = "0.cloud.chals.io"
PORT = 29513

s = socket.create_connection((HOST, PORT), timeout=10)
print(f"[+] TCP connected to {HOST}:{PORT}")

s.settimeout(1.0)

print("[*] Monitoring truth stream... (Ctrl+C to stop)")

try:
    while True:
        try:
            data = s.recv(4096)
            if not data:
                print("[*] Server closed connection.")
                break
            print(data.decode("utf-8", errors="replace").rstrip())
        except socket.timeout:
            # Keep the connection alive by sending a newline periodically.
            try:
                s.sendall(b"\n")
            except OSError:
                print("[!] Failed to send keepalive.")
                break
            continue
except KeyboardInterrupt:
    print("\n[*] Interrupted by user.")
finally:
    s.close()
    print("[*] Connection closed.")
