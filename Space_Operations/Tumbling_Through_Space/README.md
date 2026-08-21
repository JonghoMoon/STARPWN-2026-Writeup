# Tumbling Through Space

| | |
|---|---|
| **Category** | Space Operations |
| **Points** | 471 |
| **Solves** | 137 |

## Description

Sometimes a glider needs to know not to ask too many questions about who is behind a brief. This is one of those cases.

Our friends are having difficulties with one of their satellites. It appears it has been struck by space debris and is now tumbling out of control. This is where you come in. The Attitude Determination and Control System (ADCS) is still online, but the automated detumbling sequence has failed. You will have to compute the correct control torques manually.

Connect to the provided shell. You will be told the satellite's moments of inertia (Ixx, Iyy, Izz) and current angular velocities (ωx, ωy, ωz). Submit four space-separated values per line:

```
Tx Ty Tz duration
```

- `Tx/Ty/Tz` — body-frame torques in N·m
- `duration` — burn length in seconds (0 < duration ≤ 100)

The torque-vector magnitude is capped at 1.0 N·m. Detumbling succeeds when |ω| drops below 0.01 rad/s.

**Attachments:** `nc 0.cloud.chals.io <port>`

## Solution

### Steps

**1. Parse the telemetry**

The server provides moments of inertia and current angular velocity:

```
Ixx = 17.742776,  Iyy = 13.455368,  Izz = 17.491645  (kg·m²)
ωx  = +0.383487,  ωy  = -0.303548,  ωz  = +0.174217  (rad/s)
```

**2. Compute angular momentum**

```
L = I · ω   (component-wise)

Lx = Ixx × ωx = 6.804129  kg·m²/s
Ly = Iyy × ωy = -4.084344 kg·m²/s
Lz = Izz × ωz = 3.047343  kg·m²/s
|L| = 8.280 kg·m²/s
```

**3. Calculate the counter-torque**

To cancel the angular momentum in `duration` seconds:

```
T = -L / duration
```

Choose `duration` large enough so `|T| = |L| / duration ≤ 1.0 N·m`:

```
duration ≥ |L| = 8.280 s  →  use duration = 9 s

Tx = -Lx / 9 = -0.756014 N·m
Ty = -Ly / 9 = +0.453817 N·m
Tz = -Lz / 9 = -0.338594 N·m
```

**4. Submit and verify**

```
-0.756014 0.453817 -0.338594 9.0
```

After applying the torque, |ω| drops to ~0.000001 rad/s — well below the 0.01 rad/s threshold.

### Exploit Code

```python
#!/usr/bin/env python3
"""
Usage: python3 solve.py <host> <port>
"""
import math, re, socket, sys

def compute_torque(Ixx, Iyy, Izz, wx, wy, wz, max_torque=1.0, max_dur=100.0):
    Lx = Ixx * wx
    Ly = Iyy * wy
    Lz = Izz * wz
    L_mag = math.sqrt(Lx**2 + Ly**2 + Lz**2)
    dur = min(math.ceil(L_mag), max_dur)
    dur = max(dur, 1.0)
    return -Lx/dur, -Ly/dur, -Lz/dur, dur

class NCClient:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=15)
        self.buf = b""
    def recv_until(self, marker, timeout=20):
        self.sock.settimeout(timeout)
        while marker not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk: break
            self.buf += chunk
        idx = self.buf.find(marker)
        text, self.buf = self.buf[:idx+len(marker)].decode(errors="replace"), self.buf[idx+len(marker):]
        return text
    def send(self, text): self.sock.sendall(text.encode())
    def close(self): self.sock.close()

PATTERNS = {
    'Ixx': r'Ixx\s*=\s*([\d.]+)', 'Iyy': r'Iyy\s*=\s*([\d.]+)',
    'Izz': r'Izz\s*=\s*([\d.]+)', 'wx':  r'omega_x\s*=\s*([+-]?[\d.]+)',
    'wy':  r'omega_y\s*=\s*([+-]?[\d.]+)', 'wz': r'omega_z\s*=\s*([+-]?[\d.]+)',
}

nc = NCClient(sys.argv[1], int(sys.argv[2]))
text = nc.recv_until(b"Enter control torques")
p = {k: float(re.search(v, text).group(1)) for k, v in PATTERNS.items()}
Tx, Ty, Tz, dur = compute_torque(p['Ixx'], p['Iyy'], p['Izz'], p['wx'], p['wy'], p['wz'])
print(f"Submitting: {Tx:.6f} {Ty:.6f} {Tz:.6f} {dur:.1f}")
nc.send(f"{Tx:.6f} {Ty:.6f} {Tz:.6f} {dur:.1f}\n")
print(nc.recv_until(b"}"))
nc.close()
```

### Sample Session

```
Attempt 1/5  |ω| = 0.519187 rad/s
> -0.756014 0.453817 -0.338594 9.0

UPDATED TELEMETRY:
  |omega| = 0.000001 rad/s

SUCCESS! SATELLITE STABILIZED!
FLAG: STARPWN{d3tumbl3_m4st3r_sp4c3_0p5}
```

## Flag

```
STARPWN{d3tumbl3_m4st3r_sp4c3_0p5}
```
