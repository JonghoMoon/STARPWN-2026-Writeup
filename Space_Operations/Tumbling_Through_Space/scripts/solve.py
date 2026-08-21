#!/usr/bin/env python3
"""
Satellite Detumbling Auto-Solver
==================================
Connects to the nc server, reads the moments of inertia and angular velocity,
then computes and submits the control torque using T = -L / duration.

Principle
----
  Angular momentum: L = I · ω
  Control torque: T = -L / t   (applied for t seconds, driving L → 0 and ω → 0)
  Constraint: |T| ≤ 1.0 N·m  → choose duration so that t ≥ |L|

Usage
------
  python3 detumble.py <host> <port>
  python3 detumble.py 0.cloud.chals.io 10429
"""

import math
import re
import socket
import sys


# ── Physics calculation ─────────────────────────────────────────────────────────────────
def compute_torque(Ixx, Iyy, Izz, wx, wy, wz, max_torque=1.0, max_dur=100.0):
    """
    T = -L / duration  (L = I·ω)

    Choose the minimum duration that satisfies |T| ≤ max_torque.
    Also enforce the constraint duration ≤ max_dur.

    Returns
    -------
    Tx, Ty, Tz  : torque components (N·m)
    duration    : application time (s)
    """
    Lx = Ixx * wx
    Ly = Iyy * wy
    Lz = Izz * wz
    L_mag = math.sqrt(Lx**2 + Ly**2 + Lz**2)

    # |T| = |L| / dur ≤ 1.0  →  dur ≥ |L|
    # Round up to provide margin, but do not exceed max_dur
    dur = min(math.ceil(L_mag), max_dur)
    dur = max(dur, 1.0)          # Minimum duration: 1 second

    Tx = -Lx / dur
    Ty = -Ly / dur
    Tz = -Lz / dur

    return Tx, Ty, Tz, dur, L_mag


# ── netcat-style client ─────────────────────────────────────────────────────────────
class NCClient:
    def __init__(self, host, port, timeout=15.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.buf  = b""

    def recv_until(self, marker, timeout=20.0):
        self.sock.settimeout(timeout)
        while marker not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            self.buf += chunk
        idx = self.buf.find(marker)
        if idx == -1:
            text, self.buf = self.buf.decode(errors="replace"), b""
        else:
            text     = self.buf[:idx + len(marker)].decode(errors="replace")
            self.buf = self.buf[idx + len(marker):]
        return text

    def send(self, text):
        self.sock.sendall(text.encode())

    def close(self):
        self.sock.close()


# ── Parsing helpers ─────────────────────────────────────────────────────────────────────
PATTERNS = {
    'Ixx': r'Ixx\s*=\s*([\d.]+)',
    'Iyy': r'Iyy\s*=\s*([\d.]+)',
    'Izz': r'Izz\s*=\s*([\d.]+)',
    'wx':  r'omega_x\s*=\s*([+-]?[\d.]+)',
    'wy':  r'omega_y\s*=\s*([+-]?[\d.]+)',
    'wz':  r'omega_z\s*=\s*([+-]?[\d.]+)',
}

def parse_telemetry(text):
    params = {}
    for key, pat in PATTERNS.items():
        m = re.search(pat, text)
        if m:
            params[key] = float(m.group(1))
    return params

def parse_omega_mag(text):
    m = re.search(r'\|omega\|\s*=\s*([\d.]+)', text)
    return float(m.group(1)) if m else None

def parse_flag(text):
    m = re.search(r'STARPWN\{[^}]+\}', text)
    return m.group(0) if m else None

def parse_attempt(text):
    m = re.search(r'Attempt\s+(\d+)/(\d+)', text)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


# ── Main routine ─────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print("Usage: python3 detumble.py <host> <port>")
        print("Example: python3 detumble.py 0.cloud.chals.io 10429")
        sys.exit(1)

    host, port = sys.argv[1], int(sys.argv[2])
    print(f"[*] Connecting: {host}:{port}")
    nc = NCClient(host, port)

    # Receive the initial briefing
    text = nc.recv_until(b"Enter control torques")
    print(text)

    for attempt in range(1, 6):
        # Parse telemetry
        p = parse_telemetry(text)
        if len(p) < 6:
            # Read more data if no updated telemetry is available
            extra = nc.recv_until(b"Enter control torques")
            print(extra)
            text += extra
            p = parse_telemetry(text)

        if len(p) < 6:
            print(f"[!] Failed to parse parameters: {p}")
            break

        omega_mag = parse_omega_mag(text)
        att, tot  = parse_attempt(text)

        print(f"\n[*] Attempt {att}/{tot}  |ω| = {omega_mag:.6f} rad/s")
        print(f"    I  = ({p['Ixx']:.4f}, {p['Iyy']:.4f}, {p['Izz']:.4f}) kg·m²")
        print(f"    ω  = ({p['wx']:+.6f}, {p['wy']:+.6f}, {p['wz']:+.6f}) rad/s")

        if omega_mag is not None and omega_mag < 0.01:
            print("[+] |ω| < 0.01 — already stabilized")
            break

        # Compute control torque
        Tx, Ty, Tz, dur, L_mag = compute_torque(
            p['Ixx'], p['Iyy'], p['Izz'],
            p['wx'],  p['wy'],  p['wz'],
        )
        T_mag = math.sqrt(Tx**2 + Ty**2 + Tz**2)

        print(f"    L  = {L_mag:.6f} kg·m²/s")
        print(f"    T  = ({Tx:.6f}, {Ty:.6f}, {Tz:.6f}) N·m  |T|={T_mag:.4f}")
        print(f"    dur= {dur:.1f} s")

        cmd = f"{Tx:.6f} {Ty:.6f} {Tz:.6f} {dur:.1f}\n"
        print(f"[*] Submitting: {cmd.strip()}")
        nc.send(cmd)

        # Receive server response
        # On success, the response contains the flag; otherwise it contains the next-attempt prompt
        try:
            resp = nc.recv_until(b"Enter control torques", timeout=15.0)
        except Exception:
            resp = ""

        # Check for flag / success
        full = resp
        flag = parse_flag(full)
        if flag or "SUCCESS" in full or "stabilized" in full.lower() or "flag" in full.lower():
            print(full)
            if flag:
                print(f"\n[+] FLAG: {flag}")
            break

        print(full)
        text = full   # Update the text parsed on the next loop iteration

    # Try to receive any final response
    try:
        tail = nc.recv_until(b"}", timeout=5.0)
        print(tail)
        flag = parse_flag(tail)
        if flag:
            print(f"\n[+] FLAG: {flag}")
    except Exception:
        pass

    nc.close()


if __name__ == "__main__":
    main()
