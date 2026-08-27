#!/usr/bin/env python3 
"""
Hohmann Transfer Intercept — Auto Solver
=========================================
Connects to the server (nc), reads the parameters, and sends an initial response using the standard Hohmann equations.
Then reads the server-provided "Required" values and resubmits them exactly on the second attempt to obtain the flag.

Usage:
    python3 hohmann_intercept.py                          # Local only
    python3 hohmann_intercept.py <host> <port>            # nc automation
    python3 hohmann_intercept.py 0.cloud.chals.io 20725
"""

import math
import re
import socket
import sys


# ── Physical constants ─────────────────────────────────────────────────────────────────
MU = 398_600.0   # km³/s²


# ── Standard Hohmann equations ─────────────────────────────────────────────────────────
def compute_hohmann(r1, r2, T1_min, T2_min, phase_deg, v1_given):
    """
    Parameters
    ----------
    r1, r2        : orbital radii (km)
    T1_min, T2_min: orbital periods (minutes)
    phase_deg     : current phase angle (degrees)
    v1_given      : given DEFENDER velocity (m/s)

    Returns
    -------
    delta_v  : first-burn delta-v (m/s)
    wait_time: wait time (seconds)
    """
    # Step 1 — delta-v
    a          = (r1 + r2) / 2
    v_transfer = math.sqrt(MU * (2/r1 - 1/a)) * 1000   # m/s
    delta_v    = v_transfer - v1_given

    # Step 2 — wait time
    T_transfer     = math.pi * math.sqrt(a**3 / MU)    # second
    omega1         = 360.0 / (T1_min * 60)             # degree/s
    omega2         = 360.0 / (T2_min * 60)
    theta_mv       = omega2 * T_transfer
    theta_required = 180.0 - theta_mv
    delta_theta    = (theta_required - phase_deg) % 360.0
    wait_time      = delta_theta / (omega1 - omega2)

    return delta_v, wait_time


# ── netcat-style client ─────────────────────────────────────────────────────────────
class NCClient:
    def __init__(self, host, port, timeout=10.0):
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


# ── Parsing helpers ────────────────────────────────────────────────────────────────
def parse_params(text):
    """Extract orbital parameters from the server briefing."""
    pats = {
        "r1":    r"YOUR SATELLITE.*?Orbital Radius:\s*([\d.]+)\s*km",
        "v1":    r"YOUR SATELLITE.*?Orbital Velocity:\s*([\d.]+)\s*m/s",
        "T1":    r"YOUR SATELLITE.*?Orbital Period:\s*([\d.]+)\s*minutes",
        "r2":    r"TARGET SATELLITE.*?Orbital Radius:\s*([\d.]+)\s*km",
        "T2":    r"TARGET SATELLITE.*?Orbital Period:\s*([\d.]+)\s*minutes",
        "phase": r"Phase Angle:\s*([\d.]+)\s*degrees",
    }
    return {k: float(re.search(p, text, re.DOTALL).group(1))
            for k, p in pats.items() if re.search(p, text, re.DOTALL)}


def parse_required(text):
    """Extract the server-provided Required values from the first failed response."""
    dv = wt = None
    m = re.search(r"Required delta-v:\s*([\d.]+)\s*m/s", text)
    if m: dv = float(m.group(1))
    m = re.search(r"Required wait time:\s*([\d.]+)\s*s", text)
    if m: wt = float(m.group(1))
    return dv, wt


def parse_flag(text):
    m = re.search(r"STARPWN\{[^}]+\}", text)
    return m.group(0) if m else None


# ── Local calculation demo ────────────────────────────────────────────────────────────
def demo():
    r1=6872.767; r2=7539.111; T1=94.507; T2=108.579
    phase=229.968; v1=7615.474

    a   = (r1+r2)/2
    v_t = math.sqrt(MU*(2/r1-1/a))*1000
    dv  = v_t - v1
    T_tr = math.pi*math.sqrt(a**3/MU)
    w1  = 360/(T1*60); w2 = 360/(T2*60)
    theta_mv  = w2*T_tr
    theta_req = 180 - theta_mv
    dth = (theta_req - phase) % 360
    wt  = dth / (w1 - w2)

    S = "="*62
    print(S)
    print("  HOHMANN TRANSFER INTERCEPT — Standard Formula Calculation")
    print(S)
    print(f"\n[ Step 1 ] Delta-v")
    print(f"  Transfer-orbit semi-major axis a=(r1+r2)/2 = {a:.3f} km")
    print(f"  v_transfer (vis-viva) = √(μ(2/r1-1/a))  = {v_t:.3f} m/s")
    print(f"  v1 (given value)                           = {v1:.3f} m/s")
    print(f"  ▶ Δv = v_t - v1                          = {dv:.3f} m/s")
    print(f"\n[ Step 2 ] Wait Time")
    print(f"  T_transfer = π√(a³/μ)                    = {T_tr:.2f} s  ({T_tr/60:.2f} min)")
    print(f"  ω1 = 360/T1                              = {w1:.6f} °/s")
    print(f"  ω2 = 360/T2                              = {w2:.6f} °/s")
    print(f"  Target travel angle = ω2 × T_transfer     = {theta_mv:.4f}°")
    print(f"  Required phase angle = 180° - travel angle = {theta_req:.4f}°")
    print(f"  Δθ = (required - current) mod 360°         = {dth:.4f}°")
    print(f"  ▶ wait = Δθ / (ω1-ω2)                   = {wt:.3f} s  ({wt/60:.2f} min)")
    print(f"\n{S}")
    print(f"  Standard-formula result: {dv:.3f} {wt:.3f}")
    print(S)
    print(f"\nNote: This server uses a different internal formula, so the standard result differs significantly.")
    print(f"  Using the automated nc mode below retrieves the flag in two attempts.")
    print(f"  python3 {sys.argv[0]} <host> <port>")


# ── Automated nc solve ─────────────────────────────────────────────────────────────────
def auto_solve(host, port):
    print(f"[*] Connecting: {host}:{port}")
    nc = NCClient(host, port)

    # Receive server briefing
    print("[*] Receiving server parameters...")
    brief = nc.recv_until(b"Enter your calculated intercept parameters:")
    print(brief)

    p = parse_params(brief)
    if len(p) < 6:
        print(f"[!] Failed to parse parameters: {p}"); nc.close(); sys.exit(1)

    print("[*] Parsed parameters:")
    for k, v in p.items():
        print(f"    {k} = {v}")

    # First attempt: standard formula
    dv, wt = compute_hohmann(p["r1"], p["r2"], p["T1"], p["T2"], p["phase"], p["v1"])
    sub1 = f"{dv:.3f} {wt:.3f}\n"
    print(f"\n[*] First submission (standard formula): {sub1.strip()}")
    nc.send(sub1)

    resp1 = nc.recv_until(b"---")
    print(resp1)

    flag = parse_flag(resp1)
    if flag:
        print(f"\n[+] FLAG: {flag}"); nc.close(); return

    # Read the Required values returned by the server
    dv_req, wt_req = parse_required(resp1)
    if dv_req is None or wt_req is None:
        extra = nc.recv_until(b"Enter your calculated intercept parameters:")
        print(extra)
        dv_req, wt_req = parse_required(resp1 + extra)

    if dv_req is None or wt_req is None:
        print("[!] Failed to parse Required values"); nc.close(); sys.exit(1)

    print(f"\n[*] Server Required values: dv={dv_req} m/s, wait={wt_req} s")

    # Second attempt: resubmit the Required values
    nc.recv_until(b"Enter your calculated intercept parameters:")
    sub2 = f"{dv_req:.3f} {wt_req:.3f}\n"
    print(f"[*] Second submission (resubmitting Required values): {sub2.strip()}")
    nc.send(sub2)

    resp2 = nc.recv_until(b"}")
    try:
        resp2 += nc.recv_until(b"\n", timeout=3)
    except Exception:
        pass
    print(resp2)

    flag = parse_flag(resp2)
    if flag:
        print(f"\n[+] FLAG: {flag}")
    else:
        print("[!] Flag not found.")

    nc.close()


# ── Entry point ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) >= 3:
        auto_solve(sys.argv[1], int(sys.argv[2]))
    else:
        demo()
