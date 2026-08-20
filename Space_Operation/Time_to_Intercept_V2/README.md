# Time to Intercept -V2

| | |
|---|---|
| **Category** | Space Operation |
| **Points** | 494 |
| **Solves** | 65 |

## Description

An unknown aggressor satellite has been detected in a higher orbit and is threatening critical space infrastructure. Your mission: calculate a Hohmann transfer to intercept it.

Connect to the provided shell. You will be told your circular orbit altitude, the target's circular orbit altitude, and the current phase angle between you and the target. Submit two space-separated values:

```
delta_v_burn  wait_time
```

- `delta_v_burn` — Δv for the first (injection) burn, in m/s
- `wait_time` — seconds to wait before executing the burn

Grading tolerances: ±10 m/s on Δv, ±60 s on wait time. You have five attempts per connection.

**Attachments:** `nc 0.cloud.chals.io <port>`

## Solution

### Difference from V1

Unlike Time to Intercept (V1) where the server's internal constants differed from the standard formula and required a two-attempt read-back strategy, **V2 accepts the standard Hohmann formula values directly on the first attempt.**

### Steps

**1. Parse the orbital parameters**

| Parameter | Value |
|-----------|-------|
| DEFENDER-1 orbital radius r₁ | 6862.041 km |
| DEFENDER-1 orbital velocity v₁ | 7621.424 m/s |
| DEFENDER-1 orbital period T₁ | 94.286 min |
| AGGRESSOR-X orbital radius r₂ | 7431.033 km |
| AGGRESSOR-X orbital period T₂ | 106.253 min |
| Phase angle θ | 137.625° |

**2. Calculate delta-v**

```
a = (r1 + r2) / 2                         (transfer orbit semi-major axis)
v_transfer = √(μ × (2/r1 − 1/a)) × 1000  (m/s, vis-viva equation)
delta_v = v_transfer − v1
```

**3. Calculate wait time**

```
T_transfer = π × √(a³/μ)                  (half-period of transfer orbit)
ω1 = 360 / (T1 × 60)                      (°/s)
ω2 = 360 / (T2 × 60)                      (°/s)
θ_target_moves = ω2 × T_transfer
θ_required = 180° − θ_target_moves
Δθ = (θ_required − θ_current) mod 360°
wait_time = Δθ / (ω1 − ω2)
```

**4. Submit on the first attempt**

```
150.2 32454.8
→ INTERCEPT SUCCESS!
```

### Exploit Code

```python
#!/usr/bin/env python3
"""
Usage: python3 solve.py <host> <port>
"""
import math, re, socket, sys

MU = 398_600.0

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

nc = NCClient(sys.argv[1], int(sys.argv[2]))
brief = nc.recv_until(b"Enter your calculated intercept parameters:")
p = parse_params(brief)
dv, wt = compute_hohmann(p["r1"], p["r2"], p["T1"], p["T2"], p["phase"], p["v1"])
print(f"Submitting: {dv:.1f} {wt:.1f}")
nc.send(f"{dv:.1f} {wt:.1f}\n")
print(nc.recv_until(b"}"))
nc.close()
```

### Sample Session

```
Attempt 1/5
> 150.2 32454.8

Calculating intercept trajectory... 

TRAJECTORY ANALYSIS: 
Submitted delta-v: 150.200 m/s 
Submitted wait time: 32454.800 s (540.91 min) 
====================================================================== 
INTERCEPT SUCCESS! 
====================================================================== 
Excellent work! Your calculations are accurate. 
Simulating intercept sequence... 
T-540.9 minutes: Waiting for phase angle alignment... 
T-00:00: Phase angle optimal 
T+00:00: Executing burn, Δv = 150.2 m/s T+50.1 
minutes: Coast phase complete T+50.1 
minutes: Circularization burn, Δv = 147.3 m/s 
T+END: Rendezvous achieved! 
The aggressor satellite has been successfully intercepted. 
Mission accomplished. Here is your flag: STARPWN{dont_print_th3_answer_} 
======================================================================
```

## Flag

```
STARPWN{dont_print_th3_answer_}
```
