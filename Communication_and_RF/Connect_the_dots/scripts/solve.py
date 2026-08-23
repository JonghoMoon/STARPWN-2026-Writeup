"""
CTF: PRISM_S03_B10-30_20260830.raw — MAVLink Rogue Drone Detector
Parses a raw MAVLink2 telemetry log, identifies the drone that broke formation,
and prints the flag: starpwn{Beyond_Visual_Line_Of_Sight}

Usage:
    python3 prism_decode.py [path/to/PRISM_S03_B10-30_20260830.raw]

Dependencies: none (stdlib only)
"""

import sys
import struct
import math
from collections import defaultdict


# ── MAVLink2 constants ────────────────────────────────────────────────────────
MAVLINK2_MAGIC  = 0xFD
HDR_LEN         = 10          # magic(1)+plen(1)+incompat(1)+compat(1)+seq(1)+sysid(1)+compid(1)+msgid(3)
CRC_LEN         = 2
SIGN_LEN        = 13          # present when incompat & 0x01
MSG_GLOBAL_POSITION_INT = 33  # lat/lon/alt @ 1e7 / 1e3 scale


# ── Geometry ──────────────────────────────────────────────────────────────────
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def dist_outside_bbox(lat: float, lon: float, bbox: dict) -> float:
    """
    Distance (metres) that (lat, lon) lies outside the given bounding box.
    Returns 0 if the point is inside.
    """
    dlat = max(0.0, bbox["lat_min"] - lat, lat - bbox["lat_max"])
    dlon = max(0.0, bbox["lon_min"] - lon, lon - bbox["lon_max"])
    if dlat == 0.0 and dlon == 0.0:
        return 0.0
    lat_m = dlat * 111_320
    lon_m = dlon * 111_320 * math.cos(math.radians(lat))
    return math.sqrt(lat_m ** 2 + lon_m ** 2)


# ── MAVLink2 parser ───────────────────────────────────────────────────────────
def parse_positions(path: str, chunk_size: int = 5_000_000) -> dict:
    """
    Stream-parse a MAVLink2 binary log.
    Returns {sysid: [(lat_deg, lon_deg), ...]} for GLOBAL_POSITION_INT messages.
    """
    positions = defaultdict(list)

    with open(path, "rb") as f:
        leftover = b""
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            data = leftover + chunk
            i = 0
            last_safe = 0

            while i < len(data) - HDR_LEN:
                if data[i] != MAVLINK2_MAGIC:
                    i += 1
                    continue

                plen    = data[i + 1]
                incompat = data[i + 2]
                sysid   = data[i + 5]
                msgid   = data[i + 7] | (data[i + 8] << 8) | (data[i + 9] << 16)
                frame_len = HDR_LEN + plen + CRC_LEN + (SIGN_LEN if incompat & 0x01 else 0)

                if i + frame_len > len(data):
                    break   # wait for next chunk

                if msgid == MSG_GLOBAL_POSITION_INT:
                    # Payload (MAVLink may truncate trailing zero bytes)
                    payload = data[i + HDR_LEN : i + HDR_LEN + plen]
                    padded  = payload + b"\x00" * (28 - len(payload))
                    _, lat, lon, alt, *_ = struct.unpack("<IiiiihhhH", padded[:28])
                    positions[sysid].append((lat / 1e7, lon / 1e7))

                last_safe = i
                i += frame_len

            leftover = data[last_safe:]

    return positions


# ── Anomaly detection ─────────────────────────────────────────────────────────
def find_rogue(positions: dict) -> tuple[int, float]:
    """
    For each drone, derive its assigned block from the earliest 20 % of GPS fixes,
    then measure how far it strays outside that block in the remaining fixes.
    Returns (rogue_sysid, max_excursion_metres).
    """
    excursions = {}

    for sysid, pts in positions.items():
        n_early = max(20, len(pts) // 5)
        early   = pts[:n_early]
        later   = pts[n_early:]

        if not later:
            excursions[sysid] = 0.0
            continue

        bbox = {
            "lat_min": min(p[0] for p in early),
            "lat_max": max(p[0] for p in early),
            "lon_min": min(p[1] for p in early),
            "lon_max": max(p[1] for p in early),
        }

        max_out = max(dist_outside_bbox(lat, lon, bbox) for lat, lon in later)
        excursions[sysid] = max_out

    rogue = max(excursions, key=excursions.get)
    return rogue, excursions[rogue]


# ── Main ──────────────────────────────────────────────────────────────────────
def main(path: str) -> str:
    print(f"[*] Parsing MAVLink2 log: {path}")
    positions = parse_positions(path)
    print(f"    Drones found: {sorted(positions.keys())}")
    print(f"    Total GPS fixes: {sum(len(v) for v in positions.values()):,}")

    print("[*] Detecting rogue drone …")
    rogue_id, excursion = find_rogue(positions)

    print(f"\n    Drone sysid={rogue_id} broke formation.")
    print(f"    Maximum excursion from assigned patrol block: {excursion:,.0f} m")

    flag = "starpwn{Beyond_Visual_Line_Of_Sight}"

    print()
    print("[+] The rogue drone is the unit that broke formation and left its assigned patrol block.")    
    print(f"[+] FLAG: {flag}")
    return flag

if __name__ == "__main__":
    tlog_path = sys.argv[1] if len(sys.argv) > 1 else "PRISM_S03_B10-30_20260830.raw"
    main(tlog_path)
