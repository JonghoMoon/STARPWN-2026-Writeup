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

PCAP_GLOBAL_HDR = 24
PCAP_PKT_HDR    = 16
SLL2_HDR        = 20
IP_MIN          = 20
UDP_HDR         = 8
MAV_HDR         = 10

MSG_GPS_RAW_INT = 24
GPS_FIX_GOOD    = 3


def haversine(lat1, lon1, lat2, lon2):
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def circumcenter(pts):
    c_lat = sum(p[0] for p in pts) / 3
    c_lon = sum(p[1] for p in pts) / 3
    sl = 111_320
    sw = 111_320 * math.cos(math.radians(c_lat))
    xy = [((p[0] - c_lat) * sl, (p[1] - c_lon) * sw) for p in pts]
    (ax, ay), (bx, by), (cx, cy) = xy
    D = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / D
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / D
    center_lat = c_lat + uy / sl
    center_lon = c_lon + ux / sw
    radius = math.sqrt((ax - ux) ** 2 + (ay - uy) ** 2)
    return (center_lat, center_lon), radius


def extract_gps_raw_int(path):
    records = defaultdict(list)
    GPS_STRUCT = struct.Struct("<QiiiHHHHBB")
    with open(path, "rb") as f:
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
            if len(pkt) < SLL2_HDR + IP_MIN + UDP_HDR + MAV_HDR:
                continue
            ether_type = struct.unpack(">H", pkt[0:2])[0]
            if ether_type != 0x0800:
                continue
            ip = pkt[SLL2_HDR:]
            ihl = (ip[0] & 0x0F) * 4
            if ip[9] != 17:
                continue
            mv = ip[ihl + UDP_HDR:]
            if len(mv) < MAV_HDR or mv[0] != 0xFD:
                continue
            plen = mv[1]
            sysid = mv[5]
            msgid = mv[7] | (mv[8] << 8) | (mv[9] << 16)
            if msgid != MSG_GPS_RAW_INT or plen < 28:
                continue
            payload = mv[MAV_HDR : MAV_HDR + plen] + b"\x00" * (30 - plen)
            try:
                time_usec, lat, lon, alt, eph, epv, vel, cog, fix_type, sats = GPS_STRUCT.unpack(payload[:30])
            except struct.error:
                continue
            records[sysid].append((ts, lat / 1e7, lon / 1e7, fix_type, sats))
    return records


def find_last_good_fix(records):
    failures = {}
    for sysid, events in records.items():
        last_good_idx = None
        for i in range(len(events) - 1):
            if events[i][3] >= GPS_FIX_GOOD and events[i + 1][3] < GPS_FIX_GOOD:
                last_good_idx = i
        if last_good_idx is not None:
            _, lat, lon, _, _ = events[last_good_idx]
            failures[sysid] = (lat, lon)
    return failures


def main(pcap_path):
    records = extract_gps_raw_int(pcap_path)
    failures = find_last_good_fix(records)
    failure_pts = [coord for _, coord in sorted(failures.items())]
    center, radius = circumcenter(failure_pts)
    print(f"Circle center: lat={center[0]:.6f}, lon={center[1]:.6f}")
    print(f"Circle radius: {radius:.0f} m")
    print(f"FLAG: starpwn{{Echo_Trail_Park}}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "PRISM_S05_DNCN_20260831.pcap")
```

## Flag

```
starpwn{Echo_Trail_Park}
```
