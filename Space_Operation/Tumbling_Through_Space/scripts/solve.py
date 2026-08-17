#!/usr/bin/env python3
"""
Satellite Detumbling Auto-Solver
==================================
nc 서버에 접속해 관성 모멘트·각속도를 읽고,
T = -L / duration 공식으로 제어 토크를 계산·제출합니다.

원리
----
  각운동량:  L = I · ω
  제어 토크: T = -L / t   (t초 동안 적용하면 L → 0, ω → 0)
  제약:      |T| ≤ 1.0 N·m  →  t ≥ |L|  이 되도록 duration 결정

사용법
------
  python3 detumble.py <host> <port>
  python3 detumble.py 0.cloud.chals.io 10429
"""

import math
import re
import socket
import sys


# ── 물리 계산 ─────────────────────────────────────────────────────────────────
def compute_torque(Ixx, Iyy, Izz, wx, wy, wz, max_torque=1.0, max_dur=100.0):
    """
    T = -L / duration  (L = I·ω)

    duration은 |T| ≤ max_torque를 만족하는 최솟값으로 결정.
    duration ≤ max_dur 제약도 적용.

    Returns
    -------
    Tx, Ty, Tz  : 토크 (N·m)
    duration    : 적용 시간 (s)
    """
    Lx = Ixx * wx
    Ly = Iyy * wy
    Lz = Izz * wz
    L_mag = math.sqrt(Lx**2 + Ly**2 + Lz**2)

    # |T| = |L| / dur ≤ 1.0  →  dur ≥ |L|
    # 올림 정수로 여유 확보, 단 max_dur 초과 불가
    dur = min(math.ceil(L_mag), max_dur)
    dur = max(dur, 1.0)          # 최소 1초

    Tx = -Lx / dur
    Ty = -Ly / dur
    Tz = -Lz / dur

    return Tx, Ty, Tz, dur, L_mag


# ── nc 클라이언트 ─────────────────────────────────────────────────────────────
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


# ── 파싱 ─────────────────────────────────────────────────────────────────────
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


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 3:
        print("사용법: python3 detumble.py <host> <port>")
        print("예시:   python3 detumble.py 0.cloud.chals.io 10429")
        sys.exit(1)

    host, port = sys.argv[1], int(sys.argv[2])
    print(f"[*] 연결: {host}:{port}")
    nc = NCClient(host, port)

    # 초기 브리핑 수신
    text = nc.recv_until(b"Enter control torques")
    print(text)

    for attempt in range(1, 6):
        # 텔레메트리 파싱
        p = parse_telemetry(text)
        if len(p) < 6:
            # 업데이트된 텔레메트리가 없으면 더 읽기
            extra = nc.recv_until(b"Enter control torques")
            print(extra)
            text += extra
            p = parse_telemetry(text)

        if len(p) < 6:
            print(f"[!] 파라미터 파싱 실패: {p}")
            break

        omega_mag = parse_omega_mag(text)
        att, tot  = parse_attempt(text)

        print(f"\n[*] Attempt {att}/{tot}  |ω| = {omega_mag:.6f} rad/s")
        print(f"    I  = ({p['Ixx']:.4f}, {p['Iyy']:.4f}, {p['Izz']:.4f}) kg·m²")
        print(f"    ω  = ({p['wx']:+.6f}, {p['wy']:+.6f}, {p['wz']:+.6f}) rad/s")

        if omega_mag is not None and omega_mag < 0.01:
            print("[+] |ω| < 0.01 — 이미 안정화됨")
            break

        # 토크 계산
        Tx, Ty, Tz, dur, L_mag = compute_torque(
            p['Ixx'], p['Iyy'], p['Izz'],
            p['wx'],  p['wy'],  p['wz'],
        )
        T_mag = math.sqrt(Tx**2 + Ty**2 + Tz**2)

        print(f"    L  = {L_mag:.6f} kg·m²/s")
        print(f"    T  = ({Tx:.6f}, {Ty:.6f}, {Tz:.6f}) N·m  |T|={T_mag:.4f}")
        print(f"    dur= {dur:.1f} s")

        cmd = f"{Tx:.6f} {Ty:.6f} {Tz:.6f} {dur:.1f}\n"
        print(f"[*] 제출: {cmd.strip()}")
        nc.send(cmd)

        # 응답 수신
        # 성공이면 flag, 실패면 다음 attempt 프롬프트
        try:
            resp = nc.recv_until(b"Enter control torques", timeout=15.0)
        except Exception:
            resp = ""

        # flag / success 확인
        full = resp
        flag = parse_flag(full)
        if flag or "SUCCESS" in full or "stabilized" in full.lower() or "flag" in full.lower():
            print(full)
            if flag:
                print(f"\n[+] FLAG: {flag}")
            break

        print(full)
        text = full   # 다음 루프에서 파싱할 텍스트 업데이트

    # 마지막 응답 수신 시도
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
