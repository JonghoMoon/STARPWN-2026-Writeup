# Silent Beacon

| | |
|---|---|
| **Category** | Space Communication & RF |
| **Points** | 454 |
| **Solves** | 171 |

## Description

A new brief from Titan Corp, but keep this one on the down low. One of their classified CubeSats went silent after a suspected cyber intrusion. The last telemetry burst was captured at the ground station, but the file is raw, CCSDS packets buried in line noise, with multiple APIDs interleaved.

Your task is to recover the lost telemetry. More deets in the `telemetry_dictionary.json`.

**Hint:** Identify the sync markers, parse the CCSDS Space Packet headers, decode the housekeeping stream.

**Attachments:** `STARPWN2026-Silent_Beacon.zip` (`capture.bin`, `telemetry_dictionary.json`, `packet_ids.txt`)

## Solution

### Steps

**1. Scan for the Attached Sync Marker (ASM)**

Walk the raw `capture.bin` byte stream searching for the 4-byte CCSDS ASM `0x1ACFFC1D`. Each occurrence marks the start of a Space Packet.

**2. Parse the CCSDS primary header**

Each packet has a 6-byte primary header:
- Word 0: version (3b), packet type (1b), secondary header flag (1b), APID (11b)
- Word 1: sequence flags (2b), sequence count (14b)
- Word 2: data length − 1

**3. Separate packets by APID**

Three APIDs are present in the capture:

| APID | Mnemonic | Count |
|------|----------|-------|
| 50 | SYSLOG | 14 |
| 100 | HK_NOMINAL | 89 |
| 200 | ADCS_STATUS | 21 |

**4. Decode HK_NOMINAL packets**

Each APID 100 payload is 14 bytes with the following structure (`>HhhhHHBB`):

| Field | Type | Scale | Unit |
|-------|------|-------|------|
| sequence_id | uint16 | — | — |
| temp_obc | int16 | ×0.1 | °C |
| temp_battery | int16 | ×0.1 | °C |
| temp_solar | int16 | ×0.1 | °C |
| voltage_bus | uint16 | ×0.001 | V |
| current_bus | uint16 | ×0.1 | mA |
| mode | uint8 | — | enum |
| error_flags | uint8 | — | bitmask |

**5. Flag ANOMALY packets**

`error_flags` bit 7 is the `ANOMALY` flag. 29 of the 89 HK packets have this bit set.

**6. Extract the flag**

Each ANOMALY packet carries one ASCII character encoded in its `mode` byte. Sort ANOMALY packets by sequence counter and concatenate `chr(mode)` to recover the flag.

### Exploit Code

```python
#!/usr/bin/env python3
import json, struct, sys
from pathlib import Path
from typing import NamedTuple

ASM        = bytes.fromhex("1ACFFC1D")
PRIMARY_HDR = 6
APID_HK    = 100
HK_STRUCT  = struct.Struct(">HhhhHHBB")
ANOMALY_BIT = 7

class HKPacket(NamedTuple):
    seq_count: int
    mode_raw:  int
    anomaly:   bool

def parse_header(raw):
    w0 = int.from_bytes(raw[0:2], "big")
    w1 = int.from_bytes(raw[2:4], "big")
    w2 = int.from_bytes(raw[4:6], "big")
    return (w0 & 0x7FF), (w1 & 0x3FFF), w2 + 1  # apid, seq_count, data_len

def scan_packets(data):
    packets = {}
    offset = 0
    while True:
        pos = data.find(ASM, offset)
        if pos == -1: break
        offset = pos + 1
        hs = pos + len(ASM)
        if hs + PRIMARY_HDR > len(data): continue
        apid, seq, dlen = parse_header(data[hs:hs+PRIMARY_HDR])
        pe = hs + PRIMARY_HDR + dlen
        if pe > len(data): continue
        packets.setdefault(apid, []).append((seq, data[hs+PRIMARY_HDR:pe]))
    return packets

def main(capture_dir):
    raw = (capture_dir / "capture.bin").read_bytes()
    apid_packets = scan_packets(raw)
    hk_packets = []
    for seq, pl in sorted(apid_packets.get(APID_HK, []), key=lambda x: x[0]):
        if len(pl) < 14: continue
        vals = HK_STRUCT.unpack(pl[:14])
        mode_raw, error_flags = vals[6], vals[7]
        anomaly = bool(error_flags & (1 << ANOMALY_BIT))
        hk_packets.append(HKPacket(seq, mode_raw, anomaly))

    flag = "".join(chr(p.mode_raw) for p in sorted(
        (p for p in hk_packets if p.anomaly), key=lambda p: p.seq_count))
    print(f"FLAG: {flag}")

if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("STARPWN2026-Silent_Beacon"))
```

## Flag

```
STARPWN{h0us3k33p1ng_4n0m4ly}
```
