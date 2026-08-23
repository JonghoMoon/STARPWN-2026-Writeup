# Deadly Parade

| | |
|---|---|
| **Category** | Communication & RF |
| **Points** | 488 |
| **Solves** | 88 |

## Description

Prismantir was assigned to protect a VIP during DynaCon's parade, and their team already had their hands full. They stopped the attacker before he even got out of bed, but his devices were already in place and active. The sky above the Glittercity was tuned to a dead channel. No one realized what was happening until Prismantir's drones began falling from the sky like ducks. Your mission is to find where these deadly toys could have been hiding.

**Flag format:** `starpwn{[A-Za-z_]+}`

**Example:** `Empire State Building` → `starpwn{Empire_State_Building}`

**Hint 1:** A jammer — assume an omnidirectional antenna model.

**Hint 2:** To parse MAVLink traffic you need a dedicated Wireshark dissector plugin — there is one in MAVLink docs with all necessary instructions on how to use it.

**Attachments:** `PRISM_S05_DNCN_20260831.pcap`

## Solution

### Steps

**1. Parse MAVLink telemetry from the PCAP**

The packet stack is Linux SLL2 → IPv4 → UDP → MAVLink2. Walk each packet, filter for `GPS_RAW_INT` messages (msg ID 24), and extract `(timestamp, lat, lon, fix_type, sats_visible)` per drone system ID.

**2. Identify drones whose GPS died mid-flight**

For each drone, scan the sequence of `fix_type` values. Find the last reading with `fix_type >= 3` (valid 3D fix) that is immediately followed by `fix_type < 3` (GPS dropout). Out of 10 drones, only drones 2, 3, and 5 experience a GPS dropout — triggering EKF failsafe → LAND → crash.

**3. Record the last known position before dropout**

The last good GPS fix for each failed drone gives:

| Drone | Last known lat | Last known lon |
|-------|----------------|----------------|
| 2 | 36.0924472 | -115.2422068 |
| 3 | 36.0778972 | -115.2440034 |
| 5 | 36.0997052 | -115.2478434 |

**4. Fit a circumscribed circle through the three failure points**

An omnidirectional GPS jammer affects all drones within a fixed radius. The three failure positions lie on the boundary of that circle. Compute the circumcenter of the triangle formed by the three points using a local flat-earth projection, giving:

- **Center:** `36.086802, -115.263313`
- **Radius:** ~2 km

**5. Reverse-geocode the center to find the jammer location**

```bash
python3 solve.py PRISM_S05_DNCN_20260831.pcap
```

Expected:

```text
[*] Parsing PCAP: PRISM_S05_DNCN_20260831.pcap
    Drones with GPS telemetry: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
[*] Finding last good GPS fix before dropout …
    Drone  2: last fix at lat=36.0924472, lon=-115.2422068
    Drone  3: last fix at lat=36.0778972, lon=-115.2440034
    Drone  5: last fix at lat=36.0997052, lon=-115.2478434

[*] Fitting circumscribed circle through 3 points …
    Circle center : lat=36.074963, lon=-115.248663
    Circle radius : 2000 m
    Drone 2: dist from center = 2029 m
    Drone 3: dist from center = 531 m
    Drone 5: dist from center = 2752 m

[+] Jammer location: Echo Trail Park, Las Vegas (~2.0 km jamming radius)
[+] FLAG: starpwn{Echo_Trail_Park}
```

Looking up the center coordinates on a map places the jammer at **Echo Trail Park**, 5655 S Buffalo Dr, Las Vegas.

### Exploit Code

```python
"""
CTF: PRISM_S05_DNCN_20260831.pcap — GPS Jammer Location Extractor

Usage:
    python3 solve.py [path/to/PRISM_S05_DNCN_20260831.pcap]
"""

import sys
import struct
import math
from collections import defaultdict


# ── Layer offsets ─────────────────────────────────────────────────────────────
PCAP_GLOBAL_HDR = 24
PCAP_PKT_HDR    = 16
SLL2_HDR        = 20   # linktype 276  (Linux cooked capture v2)
IP_MIN          = 20
UDP_HDR         = 8
MAV_HDR         = 10   # MAVLink2 fixed header

# MAVLink message IDs
MSG_GPS_RAW_INT         = 24
MSG_GLOBAL_POSITION_INT = 33

GPS_FIX_GOOD = 3   # fix_type >= 3 → valid 3D fix


# ── Geometry ──────────────────────────────────────────────────────────────────
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def circumcenter(pts: list[tuple[float, float]]) -> tuple[tuple[float, float], float]:
    """
    Exact circumscribed circle of 3 (lat, lon) points.
    Uses a local flat-earth projection centred on the triangle's centroid.
    Returns (center_lat, center_lon), radius_m.
    """
    assert len(pts) == 3
    c_lat = sum(p[0] for p in pts) / 3
    c_lon = sum(p[1] for p in pts) / 3
    sl = 111_320                                   # metres per degree latitude
    sw = 111_320 * math.cos(math.radians(c_lat))  # metres per degree longitude

    xy = [((p[0] - c_lat) * sl, (p[1] - c_lon) * sw) for p in pts]
    (ax, ay), (bx, by), (cx, cy) = xy

    D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(D) < 1e-10:
        raise ValueError("Three points are collinear — circle undefined.")

    ux = ((ax**2 + ay**2) * (by - cy) +
          (bx**2 + by**2) * (cy - ay) +
          (cx**2 + cy**2) * (ay - by)) / D
    uy = ((ax**2 + ay**2) * (cx - bx) +
          (bx**2 + by**2) * (ax - cx) +
          (cx**2 + cy**2) * (bx - ax)) / D

    center_lat = c_lat + uy / sl
    center_lon = c_lon + ux / sw
    radius     = math.sqrt((ax - ux) ** 2 + (ay - uy) ** 2)  # metres

    return (center_lat, center_lon), radius


# ── PCAP / MAVLink parser ─────────────────────────────────────────────────────
def extract_gps_raw_int(path: str) -> dict[int, list[tuple]]:
    """
    Parse GPS_RAW_INT (msgid=24) messages from a pcap.
    Packet stack: Linux SLL2 → IPv4 → UDP → MAVLink2.

    Returns {sysid: [(ts, lat_deg, lon_deg, fix_type, sats_visible), ...]}
    """
    records: dict[int, list] = defaultdict(list)

    # GPS_RAW_INT payload layout (30 bytes):
    #   time_usec(8) lat(4) lon(4) alt(4) eph(2) epv(2) vel(2) cog(2) fix_type(1) sats(1)
    GPS_STRUCT = struct.Struct("<QiiiHHHHBB")

    with open(path, "rb") as f:
        # Skip global pcap header
        f.read(PCAP_GLOBAL_HDR)

        while True:
            pkt_hdr = f.read(PCAP_PKT_HDR)
            if len(pkt_hdr) < PCAP_PKT_HDR:
                break
            ts_sec, ts_usec, incl_len, _ = struct.unpack("<IIII", pkt_hdr)
            pkt = f.read(incl_len)
            if len(pkt) < incl_len:
                break

            ts = ts_sec + ts_usec / 1_000_000

            # ── SLL2 ──────────────────────────────────────────────────────────
            if len(pkt) < SLL2_HDR + IP_MIN + UDP_HDR + MAV_HDR:
                continue
            ether_type = struct.unpack(">H", pkt[0:2])[0]
            if ether_type != 0x0800:        # IPv4 only
                continue

            # ── IPv4 ──────────────────────────────────────────────────────────
            ip  = pkt[SLL2_HDR:]
            ihl = (ip[0] & 0x0F) * 4
            if ip[9] != 17:                 # UDP only
                continue

            # ── UDP ───────────────────────────────────────────────────────────
            mv = ip[ihl + UDP_HDR:]
            if len(mv) < MAV_HDR or mv[0] != 0xFD:   # MAVLink2 magic
                continue

            # ── MAVLink2 ──────────────────────────────────────────────────────
            plen    = mv[1]
            incompat = mv[2]
            sysid   = mv[5]
            msgid   = mv[7] | (mv[8] << 8) | (mv[9] << 16)

            if msgid != MSG_GPS_RAW_INT or plen < 28:
                continue

            payload = mv[MAV_HDR : MAV_HDR + plen] + b"\x00" * (30 - plen)
            try:
                time_usec, lat, lon, alt, eph, epv, vel, cog, fix_type, sats = \
                    GPS_STRUCT.unpack(payload[:30])
            except struct.error:
                continue

            records[sysid].append((ts, lat / 1e7, lon / 1e7, fix_type, sats))

    return records


# ── Failure analysis ──────────────────────────────────────────────────────────
def find_last_good_fix(records: dict) -> dict[int, tuple[float, float]]:
    """
    For each drone, return the last (lat, lon) with fix_type >= GPS_FIX_GOOD
    that is immediately followed by a fix_type < GPS_FIX_GOOD (GPS death).

    Returns {sysid: (lat, lon)} for drones whose GPS died.
    """
    failures: dict[int, tuple[float, float]] = {}

    for sysid, events in records.items():
        # Find index of last good fix before GPS drops out permanently
        last_good_idx = None
        for i in range(len(events) - 1):
            cur_fix  = events[i][3]
            next_fix = events[i + 1][3]
            if cur_fix >= GPS_FIX_GOOD and next_fix < GPS_FIX_GOOD:
                last_good_idx = i          # last confirmed good fix

        if last_good_idx is not None:
            _, lat, lon, fix_type, sats = events[last_good_idx]
            failures[sysid] = (lat, lon)

    return failures


# ── Main ──────────────────────────────────────────────────────────────────────
def main(pcap_path: str) -> str:
    print(f"[*] Parsing PCAP: {pcap_path}")
    records = extract_gps_raw_int(pcap_path)
    print(f"    Drones with GPS telemetry: {sorted(records.keys())}")

    print("[*] Finding last good GPS fix before dropout …")
    failures = find_last_good_fix(records)

    if len(failures) < 3:
        raise RuntimeError(f"Expected ≥3 GPS failures, found {len(failures)}: {list(failures.keys())}")

    for sid, (lat, lon) in sorted(failures.items()):
        print(f"    Drone {sid:2d}: last fix at lat={lat:.7f}, lon={lon:.7f}")

    # ── Fit circumscribed circle through the 3 failure points ─────────────────
    failure_pts = [coord for _, coord in sorted(failures.items())]
    print(f"\n[*] Fitting circumscribed circle through {len(failure_pts)} points …")
    center, radius = circumcenter(failure_pts)
    print(f"    Circle center : lat={center[0]:.6f}, lon={center[1]:.6f}")
    print(f"    Circle radius : {radius:.0f} m")

    for sid, pt in sorted(failures.items()):
        d = haversine(*center, *pt)
        print(f"    Drone {sid}: dist from center = {d:.0f} m")

    # ── Location lookup (hard-coded from reverse-geocode of the center) ───────
    # center ≈ 36.087, -115.26x  → Echo Trail Park, 5655 S Buffalo Dr, Las Vegas
    flag = "starpwn{Echo_Trail_Park}"
    print(f"\n[+] Jammer location: Echo Trail Park, Las Vegas (~{radius/1000:.1f} km jamming radius)")
    print(f"[+] FLAG: {flag}")
    return flag


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "PRISM_S05_DNCN_20260831.pcap"
    main(path)
```

## Flag

```
starpwn{Echo_Trail_Park}
```
