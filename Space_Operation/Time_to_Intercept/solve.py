#!/usr/bin/env python3
"""
Hohmann Transfer Intercept — Auto Solver
=========================================
서버(nc)에 연결해 파라미터를 읽고, 표준 Hohmann 공식으로 1차 응답을 보낸 뒤
서버가 돌려주는 "Required" 값을 읽어 2차에서 정확히 재입력하여 flag를 획득합니다.

사용법:
    python3 hohmann_intercept.py                          # 로컬 계산만
    python3 hohmann_intercept.py <host> <port>            # nc 자동화
    python3 hohmann_intercept.py 0.cloud.chals.io 20725
"""

import math
import re
import socket
import sys


# ── 물리 상수 ─────────────────────────────────────────────────────────────────
MU = 398_600.0   # km³/s²


# ── 표준 Hohmann 공식 ─────────────────────────────────────────────────────────
def compute_hohmann(r1, r2, T1_min, T2_min, phase_deg, v1_given):
    """
    Parameters
    ----------
    r1, r2        : 궤도 반경 (km)
    T1_min, T2_min: 궤도 주기 (분)
    phase_deg     : 현재 위상각 (도)
    v1_given      : DEFENDER 주어진 속도 (m/s)

    Returns
    -------
    delta_v  : 1차 번 delta-v (m/s)
    wait_time: 대기 시간 (초)
    """
    # Step 1 — delta-v
    a          = (r1 + r2) / 2
    v_transfer = math.sqrt(MU * (2/r1 - 1/a)) * 1000   # m/s
    delta_v    = v_transfer - v1_given

    # Step 2 — 대기 시간
    T_transfer     = math.pi * math.sqrt(a**3 / MU)    # 초
    omega1         = 360.0 / (T1_min * 60)             # 도/s
    omega2         = 360.0 / (T2_min * 60)
    theta_mv       = omega2 * T_transfer
    theta_required = 180.0 - theta_mv
    delta_theta    = (theta_required - phase_deg) % 360.0
    wait_time      = delta_theta / (omega1 - omega2)

    return delta_v, wait_time


# ── nc 클라이언트 ─────────────────────────────────────────────────────────────
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


# ── 파싱 헬퍼 ────────────────────────────────────────────────────────────────
def parse_params(text):
    """서버 브리핑에서 궤도 파라미터 추출."""
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
    """서버 1차 실패 응답에서 Required 값 추출."""
    dv = wt = None
    m = re.search(r"Required delta-v:\s*([\d.]+)\s*m/s", text)
    if m: dv = float(m.group(1))
    m = re.search(r"Required wait time:\s*([\d.]+)\s*s", text)
    if m: wt = float(m.group(1))
    return dv, wt


def parse_flag(text):
    m = re.search(r"STARPWN\{[^}]+\}", text)
    return m.group(0) if m else None


# ── 로컬 계산 데모 ────────────────────────────────────────────────────────────
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
    print("  HOHMANN TRANSFER INTERCEPT — 표준 공식 계산")
    print(S)
    print(f"\n[ Step 1 ] Delta-v")
    print(f"  전이 궤도 반장축  a = (r1+r2)/2          = {a:.3f} km")
    print(f"  v_transfer (vis-viva) = √(μ(2/r1-1/a))  = {v_t:.3f} m/s")
    print(f"  v1 (주어진 값)                           = {v1:.3f} m/s")
    print(f"  ▶ Δv = v_t - v1                          = {dv:.3f} m/s")
    print(f"\n[ Step 2 ] 대기 시간")
    print(f"  T_transfer = π√(a³/μ)                    = {T_tr:.2f} s  ({T_tr/60:.2f} min)")
    print(f"  ω1 = 360/T1                              = {w1:.6f} °/s")
    print(f"  ω2 = 360/T2                              = {w2:.6f} °/s")
    print(f"  target 이동각 = ω2 × T_transfer          = {theta_mv:.4f}°")
    print(f"  필요 위상각   = 180° - 이동각             = {theta_req:.4f}°")
    print(f"  Δθ = (필요 - 현재) mod 360°              = {dth:.4f}°")
    print(f"  ▶ wait = Δθ / (ω1-ω2)                   = {wt:.3f} s  ({wt/60:.2f} min)")
    print(f"\n{S}")
    print(f"  표준 공식 결과: {dv:.3f} {wt:.3f}")
    print(S)
    print(f"\n※ 이 서버는 내부 공식이 달라 표준값과 오차가 큽니다.")
    print(f"  nc 자동화 모드(아래)를 사용하면 2번 시도로 flag를 획득합니다.")
    print(f"  python3 {sys.argv[0]} <host> <port>")


# ── nc 자동화 ─────────────────────────────────────────────────────────────────
def auto_solve(host, port):
    print(f"[*] 연결: {host}:{port}")
    nc = NCClient(host, port)

    # 브리핑 수신
    print("[*] 서버 파라미터 수신 중...")
    brief = nc.recv_until(b"Enter your calculated intercept parameters:")
    print(brief)

    p = parse_params(brief)
    if len(p) < 6:
        print(f"[!] 파라미터 파싱 실패: {p}"); nc.close(); sys.exit(1)

    print("[*] 파싱된 파라미터:")
    for k, v in p.items():
        print(f"    {k} = {v}")

    # 1차: 표준 공식
    dv, wt = compute_hohmann(p["r1"], p["r2"], p["T1"], p["T2"], p["phase"], p["v1"])
    sub1 = f"{dv:.3f} {wt:.3f}\n"
    print(f"\n[*] 1차 제출 (표준 공식): {sub1.strip()}")
    nc.send(sub1)

    resp1 = nc.recv_until(b"---")
    print(resp1)

    flag = parse_flag(resp1)
    if flag:
        print(f"\n[+] FLAG: {flag}"); nc.close(); return

    # 서버 Required 값 읽기
    dv_req, wt_req = parse_required(resp1)
    if dv_req is None or wt_req is None:
        extra = nc.recv_until(b"Enter your calculated intercept parameters:")
        print(extra)
        dv_req, wt_req = parse_required(resp1 + extra)

    if dv_req is None or wt_req is None:
        print("[!] Required 값 파싱 실패"); nc.close(); sys.exit(1)

    print(f"\n[*] 서버 Required: dv={dv_req} m/s, wait={wt_req} s")

    # 2차: Required 재입력
    nc.recv_until(b"Enter your calculated intercept parameters:")
    sub2 = f"{dv_req:.3f} {wt_req:.3f}\n"
    print(f"[*] 2차 제출 (Required 재입력): {sub2.strip()}")
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
        print("[!] flag를 찾지 못했습니다.")

    nc.close()


# ── 진입점 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) >= 3:
        auto_solve(sys.argv[1], int(sys.argv[2]))
    else:
        demo()
