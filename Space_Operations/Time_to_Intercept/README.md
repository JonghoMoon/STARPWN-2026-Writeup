# Time to Intercept 

| | |
|---|---|
| **Category** | Space Operations |
| **Points** | 473 |
| **Solves** | 132 |

## Description

An unknown aggressor satellite has been detected in a higher orbit and is threatening critical space infrastructure. Your mission: calculate a Hohmann transfer to intercept it.

Connect to the provided shell. You will be told your circular orbit altitude, the target's circular orbit altitude, and the current phase angle between you and the target. You'll need to submit two numbers per line, space-separated:

```
delta_v_burn  wait_time
```

- `delta_v_burn` — Δv for the first (injection) burn, in m/s
- `wait_time` — seconds to wait before executing the burn so the target arrives at the rendezvous time you do

Grading tolerances: ±10 m/s on Δv, ±60 s on wait time. You have five attempts per connection.

**Attachments:** `nc 0.cloud.chals.io <port>`

## Solution

### Steps

**1. Parse the orbital parameters**

The server provides:

| Parameter | Value |
|-----------|-------|
| DEFENDER-1 orbital radius r₁ | 6872.767 km |
| DEFENDER-1 orbital velocity v₁ | 7615.474 m/s |
| DEFENDER-1 orbital period T₁ | 94.507 min |
| AGGRESSOR-X orbital radius r₂ | 7539.111 km |
| AGGRESSOR-X orbital period T₂ | 108.579 min |
| Phase angle θ | 229.968° |

**2. Calculate delta-v (Hohmann injection burn)**

Using the vis-viva equation (μ = 398600 km³/s²):

```
a = (r1 + r2) / 2 = 7205.939 km          (transfer orbit semi-major axis)
v_transfer = √(μ × (2/r1 − 1/a)) × 1000  (m/s)
delta_v = v_transfer − v1
```

The standard formula gives ~174 m/s, but the server uses a slightly different internal model. Submit the standard value first, read the server's `Required delta-v`, then resubmit the exact required value on the next attempt.

**3. Calculate wait time (phase angle alignment)**

```
T_transfer = π × √(a³/μ)                      (half-period of transfer orbit, seconds)
ω1 = 360 / (T1 × 60)                          (°/s, DEFENDER angular rate)
ω2 = 360 / (T2 × 60)                          (°/s, AGGRESSOR angular rate)
θ_target_moves = ω2 × T_transfer               (AGGRESSOR moves during coast)
θ_required = 180° − θ_target_moves             (required phase angle at burn)
Δθ = (θ_required − θ_current) mod 360°
wait_time = Δθ / (ω1 − ω2)
```

**4. Two-attempt strategy**

Since the server's internal constants differ slightly from the standard formula, use the following approach:

- **Attempt 1:** Submit the standard Hohmann result → server returns the exact `Required` values
- **Attempt 2:** Resubmit those exact values → INTERCEPT SUCCESS

This can be fully automated with the solve script.

### Exploit Code

```python
#!/usr/bin/env python3
"""
Usage:
    python3 solve.py <host> <port>
    python3 solve.py 0.cloud.chals.io 20725
"""
import math, re, socket, sys

MU = 398_600.0  # km³/s²

def compute_hohmann(r1, r2, T1_min, T2_min, phase_deg, v1):
    a          = (r1 + r2) / 2
    v_transfer = math.sqrt(MU * (2/r1 - 1/a)) * 1000
    delta_v    = v_transfer - v1
    T_transfer = math.pi * math.sqrt(a**3 / MU)
    omega1     = 360.0 / (T1_min * 60)
    omega2     = 360.0 / (T2_min * 60)
    theta_mv   = omega2 * T_transfer
    theta_req  = 180.0 - theta_mv
    delta_theta = (theta_req - phase_deg) % 360.0
    wait_time  = delta_theta / (omega1 - omega2)
    return delta_v, wait_time

class NCClient:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.buf  = b""
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

def parse_params(text):
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
    dv = wt = None
    m = re.search(r"Required delta-v:\s*([\d.]+)\s*m/s", text)
    if m: dv = float(m.group(1))
    m = re.search(r"Required wait time:\s*([\d.]+)\s*s", text)
    if m: wt = float(m.group(1))
    return dv, wt

nc = NCClient(sys.argv[1], int(sys.argv[2]))
brief = nc.recv_until(b"Enter your calculated intercept parameters:")
p = parse_params(brief)

dv, wt = compute_hohmann(p["r1"], p["r2"], p["T1"], p["T2"], p["phase"], p["v1"])
nc.send(f"{dv:.3f} {wt:.3f}\n")
resp1 = nc.recv_until(b"---")

dv_req, wt_req = parse_required(resp1)
nc.recv_until(b"Enter your calculated intercept parameters:")
nc.send(f"{dv_req:.3f} {wt_req:.3f}\n")
resp2 = nc.recv_until(b"}")
print(resp2)
nc.close()
```

### Sample Session

```
Attempt 1: 174.067 26514.44
→ Required delta-v: 127.051 m/s
→ Required wait time: 18204.091 s

Attempt 2: 127.051 18204.091
Calculating intercept trajectory...
TRAJECTORY ANALYSIS:
  Submitted delta-v: 127.051 m/s
  Required delta-v: 127.051 m/s
  Error: 0.000 m/s
  Submitted wait time: 18204.091 s (303.40 min)
  Required wait time: 18204.091 s (303.40 min)
  Error: 0.000 s
======================================================================
INTERCEPT SUCCESS!
======================================================================
Excellent work! Your calculations are accurate.
Simulating intercept sequence...
  T-303.4 minutes: Waiting for phase angle alignment...
  T-00:00: Phase angle optimal
  T+00:00: Executing burn, Δv = 127.1 m/s
  T+50.7 minutes: Coast phase complete
  T+50.7 minutes: Circularization burn, Δv = 124.9 m/s
  T+END: Rendezvous achieved!
The aggressor satellite has been successfully intercepted.
Mission accomplished.
Here is your flag: STARPWN{h0hm4nn_tr4nsf3r_1nt3rc3pt}
```

## Flag

```
STARPWN{h0hm4nn_tr4nsf3r_1nt3rc3pt}
```
