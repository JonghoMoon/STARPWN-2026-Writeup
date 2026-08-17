#!/usr/bin/env python3
"""
CTF: STARPWN2026 – Silent Beacon
Extracts the flag from a raw CCSDS telemetry capture.

Solve path
----------
1. Scan capture.bin for the 4-byte Attached Sync Marker (ASM) 0x1ACFFC1D.
2. Parse the 6-byte CCSDS Space Packet primary header at each sync mark.
3. Separate packets by APID (50 = SYSLOG, 100 = HK_NOMINAL, 200 = ADCS_STATUS).
4. Decode APID 100 payloads using telemetry_dictionary.json field definitions.
5. Flag packets where error_flags bit 7 (ANOMALY) is set.
6. Assemble the flag: the `mode` byte of each ANOMALY packet – sorted by sequence
   counter – encodes one ASCII character.

Usage
-----
    python3 silent_beacon_decode.py [capture_dir]

    capture_dir defaults to "STARPWN2026-Silent_Beacon" (relative to CWD).
    It must contain capture.bin and telemetry_dictionary.json.

Flag
----
    STARPWN{h0us3k33p1ng_4n0m4ly}
"""

import json
import struct
import sys
from pathlib import Path
from typing import NamedTuple


# ── CCSDS constants ───────────────────────────────────────────────────────────
ASM           = bytes.fromhex("1ACFFC1D")   # Attached Sync Marker
PRIMARY_HDR   = 6                            # bytes
SEQ_FLAG_UNSEGMENTED = 0b11                  # standalone packet

# APID assignments (from packet_ids.txt)
APID_SYSLOG = 50
APID_HK     = 100
APID_ADCS   = 200

# HK payload layout (from telemetry_dictionary.json)
HK_STRUCT = struct.Struct(">HhhhHHBB")      # 14 bytes
HK_FIELDS = [
    "sequence_id", "temp_obc", "temp_battery",
    "temp_solar",  "voltage_bus", "current_bus",
    "mode",        "error_flags",
]
HK_SCALES  = dict(temp_obc=0.1, temp_battery=0.1, temp_solar=0.1,
                  voltage_bus=0.001, current_bus=0.1)
HK_UNITS   = dict(temp_obc="°C", temp_battery="°C", temp_solar="°C",
                  voltage_bus="V", current_bus="mA")
MODE_ENUM  = {0:"SAFE",1:"NOMINAL",2:"SCIENCE",3:"COMMS",
              4:"ATTITUDE",5:"THERMAL",6:"POWER",7:"DIAGNOSTIC"}
ERROR_BITS = ["TEMP_WARN","VOLTAGE_WARN","CURRENT_WARN","COMM_DROP",
              "TIMING_SKEW","SENSOR_DRIFT","WATCHDOG_RESET","ANOMALY"]
ANOMALY_BIT = 7


# ── Data classes ──────────────────────────────────────────────────────────────
class CCSDSHeader(NamedTuple):
    version:    int
    pkt_type:   int          # 0 = telemetry
    sec_hdr:    int
    apid:       int
    seq_flags:  int
    seq_count:  int
    data_len:   int          # payload length in bytes (data_length_field + 1)


class HKPacket(NamedTuple):
    seq_count:    int
    sequence_id:  int
    temp_obc:     float      # °C
    temp_battery: float      # °C
    temp_solar:   float      # °C
    voltage_bus:  float      # V
    current_bus:  float      # mA
    mode_raw:     int
    mode_str:     str
    error_flags:  int
    active_flags: list[str]
    anomaly:      bool


# ── CCSDS parser ──────────────────────────────────────────────────────────────
def parse_header(raw: bytes) -> CCSDSHeader:
    """Parse a 6-byte CCSDS Space Packet primary header."""
    w0 = int.from_bytes(raw[0:2], "big")
    w1 = int.from_bytes(raw[2:4], "big")
    w2 = int.from_bytes(raw[4:6], "big")
    return CCSDSHeader(
        version   = (w0 >> 13) & 0x7,
        pkt_type  = (w0 >> 12) & 0x1,
        sec_hdr   = (w0 >> 11) & 0x1,
        apid      = w0 & 0x7FF,
        seq_flags = (w1 >> 14) & 0x3,
        seq_count = w1 & 0x3FFF,
        data_len  = w2 + 1,         # CCSDS: field stores (length − 1)
    )


def scan_packets(data: bytes) -> dict[int, list[tuple[int, bytes]]]:
    """
    Walk the byte stream looking for ASM markers.
    Returns {apid: [(seq_count, payload), ...]} in capture order.
    """
    packets: dict[int, list] = {}
    offset = 0
    while True:
        pos = data.find(ASM, offset)
        if pos == -1:
            break
        offset = pos + 1                    # advance past this marker

        hdr_start = pos + len(ASM)
        if hdr_start + PRIMARY_HDR > len(data):
            continue

        hdr   = parse_header(data[hdr_start : hdr_start + PRIMARY_HDR])
        pl_start = hdr_start + PRIMARY_HDR
        pl_end   = pl_start + hdr.data_len

        if pl_end > len(data):
            continue                        # truncated packet — skip

        payload = data[pl_start:pl_end]
        packets.setdefault(hdr.apid, []).append((hdr.seq_count, payload))

    return packets


# ── Telemetry decoders ────────────────────────────────────────────────────────
def decode_hk(seq_count: int, payload: bytes) -> HKPacket | None:
    """Decode a 14-byte HK_NOMINAL payload."""
    if len(payload) < 14:
        return None
    (sequence_id, temp_obc_raw, temp_bat_raw, temp_sol_raw,
     vbus_raw, ibus_raw, mode_raw, error_flags) = HK_STRUCT.unpack(payload[:14])

    active = [ERROR_BITS[b] for b in range(8) if error_flags & (1 << b)]

    return HKPacket(
        seq_count    = seq_count,
        sequence_id  = sequence_id,
        temp_obc     = temp_obc_raw   * 0.1,
        temp_battery = temp_bat_raw   * 0.1,
        temp_solar   = temp_sol_raw   * 0.1,
        voltage_bus  = vbus_raw       * 0.001,
        current_bus  = ibus_raw       * 0.1,
        mode_raw     = mode_raw,
        mode_str     = MODE_ENUM.get(mode_raw, f"UNK({mode_raw})"),
        error_flags  = error_flags,
        active_flags = active,
        anomaly      = bool(error_flags & (1 << ANOMALY_BIT)),
    )


def decode_syslog(payload: bytes) -> str:
    return payload.decode("ascii", errors="replace").rstrip()


# ── Flag extraction ───────────────────────────────────────────────────────────
def extract_flag(hk_packets: list[HKPacket]) -> str:
    """
    Each ANOMALY packet carries one ASCII character in its `mode` byte.
    Sort by seq_count and concatenate.
    """
    anomaly_pkts = sorted(
        (p for p in hk_packets if p.anomaly),
        key=lambda p: p.seq_count,
    )
    return "".join(chr(p.mode_raw) for p in anomaly_pkts)


# ── Main ──────────────────────────────────────────────────────────────────────
def main(capture_dir: Path) -> int:
    capture_bin = capture_dir / "capture.bin"
    dict_json   = capture_dir / "telemetry_dictionary.json"

    if not capture_bin.exists():
        print(f"[!] {capture_bin} not found", file=sys.stderr)
        return 1

    print(f"[*] Reading {capture_bin}  ({capture_bin.stat().st_size:,} bytes)")
    raw = capture_bin.read_bytes()

    # Load telemetry dictionary (informational; struct already hard-coded above)
    tm_dict: dict = {}
    if dict_json.exists():
        tm_dict = json.loads(dict_json.read_text())
        print(f"[*] Telemetry dictionary version: {tm_dict.get('version', '?')}")

    # ── Step 1-2: sync scan + header parse ───────────────────────────────────
    print("[*] Scanning for ASM 0x1ACFFC1D …")
    apid_packets = scan_packets(raw)

    for apid, pkts in sorted(apid_packets.items()):
        mnemo = {APID_SYSLOG:"SYSLOG", APID_HK:"HK_NOMINAL",
                 APID_ADCS:"ADCS_STATUS"}.get(apid, f"APID_{apid}")
        print(f"    APID {apid:3d} ({mnemo}): {len(pkts)} packets")

    # ── Step 3: SYSLOG ───────────────────────────────────────────────────────
    syslog_pkts = sorted(apid_packets.get(APID_SYSLOG, []), key=lambda x: x[0])
    if syslog_pkts:
        print(f"\n[*] SYSLOG messages ({len(syslog_pkts)}):")
        for seq, pl in syslog_pkts:
            print(f"    [{seq:3d}] {decode_syslog(pl)}")

    # ── Step 4: decode HK_NOMINAL ────────────────────────────────────────────
    hk_raw = sorted(apid_packets.get(APID_HK, []), key=lambda x: x[0])
    hk_packets: list[HKPacket] = []
    for seq, pl in hk_raw:
        pkt = decode_hk(seq, pl)
        if pkt:
            hk_packets.append(pkt)

    print(f"\n[*] HK_NOMINAL packets decoded: {len(hk_packets)}")
    print(f"    {'seq':>4}  {'T_obc':>7}  {'T_bat':>7}  {'T_sol':>7}  "
          f"{'Vbus':>7}  {'Ibus':>8}  {'mode':<12}  flags")
    print("    " + "-" * 80)
    for p in hk_packets:
        flag_str = "|".join(p.active_flags) if p.active_flags else "NONE"
        mark     = "  ← ANOMALY" if p.anomaly else ""
        print(f"    {p.seq_count:>4d}  {p.temp_obc:>6.1f}C  {p.temp_battery:>6.1f}C  "
              f"{p.temp_solar:>6.1f}C  {p.voltage_bus:>6.3f}V  {p.current_bus:>6.1f}mA  "
              f"{p.mode_str:<12}  {flag_str}{mark}")

    # ── Step 5-6: flag extraction ─────────────────────────────────────────────
    anomaly_count = sum(1 for p in hk_packets if p.anomaly)
    print(f"\n[*] ANOMALY packets: {anomaly_count}")

    flag = extract_flag(hk_packets)
    if not (flag.startswith("STARPWN{") and flag.endswith("}")):
        print(f"[!] Assembled string doesn't look like a flag: {flag!r}", file=sys.stderr)
        return 2

    print(f"\n[+] FLAG: {flag}")
    return 0


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("STARPWN2026-Silent_Beacon")
    sys.exit(main(base))
