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

```bash
python3 solve.py STARPWN2026-Silent_Beacon
```

Result:

```text
[*] Reading STARPWN2026-Silent_Beacon/capture.bin  (5,835 bytes)
[*] Telemetry dictionary version: 0.4
[*] Scanning for ASM 0x1ACFFC1D …
    APID  50 (SYSLOG): 14 packets
    APID 100 (HK_NOMINAL): 89 packets
    APID 200 (ADCS_STATUS): 21 packets

[*] SYSLOG messages (14):
    [  0] BATT CHARGE 87%
    [  1] INIT OK
    [  2] WHEEL DESAT COMPLETE
    [  3] INIT OK
    [  4] WHEEL DESAT COMPLETE
    [  5] PAYLOAD HEATER OFF
    [  6] INIT OK
    [  7] BATT CHARGE 87%
    [  8] GPS LOCK 4SVS
    [  9] BATT CHARGE 87%
    [ 10] SAFE MODE EXIT
    [ 11] COMMS LINK UP
    [ 12] MODE TRANSITION NOMINAL->SCIENCE
    [ 13] SUN VECTOR ACQUIRED

[*] HK_NOMINAL packets decoded: 89
     seq    T_obc    T_bat    T_sol     Vbus      Ibus  mode          flags
    --------------------------------------------------------------------------------
       0    16.1C    18.6C    46.4C   7.545V    18.3mA  SAFE          NONE
       1    18.1C    16.2C     2.9C   7.366V    13.2mA  ATTITUDE      NONE
       2    22.9C    18.0C    22.9C   7.377V    15.4mA  UNK(83)       VOLTAGE_WARN|COMM_DROP|TIMING_SKEW|ANOMALY  ← ANOMALY
       3    27.5C    13.5C   -33.1C   7.453V    13.3mA  NOMINAL       NONE
       4    25.7C    14.5C   -98.1C   7.536V    11.0mA  DIAGNOSTIC    TEMP_WARN
       5    15.9C    20.7C     0.0C   7.379V    16.6mA  THERMAL       TEMP_WARN|SENSOR_DRIFT
       6    18.6C    18.4C    89.3C   7.518V    17.0mA  POWER         TEMP_WARN
       7    27.2C    16.8C  -124.0C   7.300V    13.5mA  NOMINAL       NONE
       8    20.1C    16.9C   129.4C   7.473V    13.6mA  UNK(84)       TEMP_WARN|COMM_DROP|SENSOR_DRIFT|WATCHDOG_RESET|ANOMALY  ← ANOMALY
       9    21.1C    18.3C    19.5C   7.400V    17.9mA  POWER         NONE
      10    21.4C    19.8C    22.3C   7.425V    14.3mA  SCIENCE       TEMP_WARN
      11    19.8C    14.9C  -141.0C   7.360V     9.3mA  NOMINAL       TIMING_SKEW
      12    23.4C    22.2C   -50.8C   7.451V    15.1mA  UNK(65)       TIMING_SKEW|ANOMALY  ← ANOMALY
      13    22.8C    16.6C    82.7C   7.443V    15.5mA  THERMAL       CURRENT_WARN
      14    18.9C    21.3C    84.8C   7.347V    14.6mA  UNK(82)       TEMP_WARN|COMM_DROP|TIMING_SKEW|SENSOR_DRIFT|ANOMALY  ← ANOMALY
      15    19.3C    18.1C    -4.5C   7.587V    19.2mA  UNK(80)       COMM_DROP|ANOMALY  ← ANOMALY
      16    23.4C    18.7C  -104.9C   7.274V    19.4mA  POWER         CURRENT_WARN
      17    22.2C    15.6C    37.1C   7.308V    21.1mA  UNK(87)       TEMP_WARN|VOLTAGE_WARN|COMM_DROP|ANOMALY  ← ANOMALY
      18    17.4C    15.5C   -28.2C   7.485V    16.6mA  NOMINAL       TEMP_WARN|SENSOR_DRIFT
      19    21.4C    15.9C    21.1C   7.404V    18.0mA  UNK(78)       TEMP_WARN|COMM_DROP|TIMING_SKEW|SENSOR_DRIFT|ANOMALY  ← ANOMALY
      20    24.7C    17.9C    91.0C   7.378V    15.3mA  UNK(123)      CURRENT_WARN|TIMING_SKEW|ANOMALY  ← ANOMALY
      21    20.5C    16.6C    92.7C   7.432V    13.9mA  THERMAL       NONE
      22    22.0C    18.1C   -43.5C   7.329V    20.4mA  UNK(104)      COMM_DROP|TIMING_SKEW|SENSOR_DRIFT|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      23    19.0C    17.2C    -5.9C   7.282V    15.5mA  DIAGNOSTIC    NONE
      24    25.8C    19.4C   -15.4C   7.458V    15.1mA  UNK(48)       VOLTAGE_WARN|SENSOR_DRIFT|ANOMALY  ← ANOMALY
      25    19.9C    16.9C    42.3C   7.419V    16.8mA  UNK(117)      CURRENT_WARN|COMM_DROP|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      26    24.3C    13.1C   -21.2C   7.350V    16.6mA  POWER         CURRENT_WARN
      27    20.7C    19.5C   -10.9C   7.363V    16.6mA  SCIENCE       NONE
      28    22.0C    25.2C    22.8C   7.398V    20.1mA  NOMINAL       NONE
      29    23.3C    16.7C   -27.5C   7.667V    16.0mA  NOMINAL       NONE
      30    27.0C    16.2C    44.3C   7.405V    15.0mA  ATTITUDE      TEMP_WARN
      31    23.2C    15.7C    46.2C   7.311V    13.6mA  UNK(115)      TEMP_WARN|VOLTAGE_WARN|COMM_DROP|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      32    26.9C    19.9C    -7.6C   7.258V    15.6mA  SCIENCE       NONE
      33    19.8C    17.2C   -22.8C   7.461V     9.2mA  NOMINAL       NONE
      34    15.0C    22.0C   -46.8C   7.499V    13.7mA  SAFE          NONE
      35    20.9C    15.2C   -44.7C   7.427V    11.2mA  UNK(51)       COMM_DROP|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      36    23.0C    16.3C    27.4C   7.524V    14.7mA  SCIENCE       NONE
      37    19.8C    24.1C   -10.0C   7.439V    16.3mA  POWER         NONE
      38    21.5C    19.2C    49.0C   7.288V    16.6mA  UNK(107)      TEMP_WARN|VOLTAGE_WARN|ANOMALY  ← ANOMALY
      39    22.0C    17.0C   -33.5C   7.548V     8.8mA  UNK(51)       TEMP_WARN|VOLTAGE_WARN|CURRENT_WARN|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      40    22.7C    22.4C   -70.3C   7.306V    21.2mA  NOMINAL       NONE
      41    21.4C    17.9C   -37.4C   7.445V    10.9mA  NOMINAL       NONE
      42    22.9C    20.0C    88.4C   7.487V    18.5mA  UNK(51)       CURRENT_WARN|COMM_DROP|TIMING_SKEW|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      43    24.4C    16.9C   -55.2C   7.407V    13.4mA  UNK(112)      CURRENT_WARN|COMM_DROP|ANOMALY  ← ANOMALY
      44    24.5C    21.3C    38.5C   7.359V    12.9mA  UNK(49)       VOLTAGE_WARN|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      45    25.5C    17.6C   -26.5C   7.257V    15.5mA  ATTITUDE      NONE
      46    24.3C    18.1C  -150.0C   7.320V    17.0mA  SCIENCE       NONE
      47    27.0C    20.2C   -12.7C   7.455V    15.0mA  NOMINAL       NONE
      48    18.3C    14.3C     2.0C   7.473V    15.3mA  SCIENCE       NONE
      49    19.7C    19.6C    75.7C   7.367V    17.6mA  UNK(110)      TEMP_WARN|CURRENT_WARN|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      50    12.6C    16.6C    32.7C   7.592V    14.8mA  THERMAL       TEMP_WARN
      51    18.5C    16.3C    15.1C   7.449V    12.2mA  POWER         TEMP_WARN|SENSOR_DRIFT
      52    24.6C    17.1C    21.2C   7.562V    13.4mA  UNK(103)      VOLTAGE_WARN|TIMING_SKEW|SENSOR_DRIFT|ANOMALY  ← ANOMALY
      53    21.3C    17.5C    77.5C   7.321V    10.3mA  SCIENCE       NONE
      54    17.5C    16.5C   -59.9C   7.442V    21.2mA  UNK(95)       VOLTAGE_WARN|CURRENT_WARN|TIMING_SKEW|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      55    20.1C    18.3C  -125.3C   7.600V    15.2mA  UNK(52)       TEMP_WARN|VOLTAGE_WARN|TIMING_SKEW|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      56    21.1C    15.6C    41.4C   7.415V    13.6mA  POWER         NONE
      57    20.1C    23.2C    56.9C   7.431V    13.4mA  ATTITUDE      NONE
      58    19.7C    14.7C    40.1C   7.245V    10.0mA  DIAGNOSTIC    NONE
      59    20.8C    17.8C    76.0C   7.267V    14.4mA  ATTITUDE      NONE
      60    19.2C    18.9C    65.9C   7.427V    12.6mA  UNK(110)      VOLTAGE_WARN|TIMING_SKEW|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      61    26.2C    20.7C     0.4C   7.604V    15.3mA  SAFE          NONE
      62    21.2C    20.3C    28.2C   7.466V    18.7mA  ATTITUDE      NONE
      63    26.7C    19.9C   -37.3C   7.545V    14.7mA  COMMS         NONE
      64    20.6C    17.8C   -81.2C   7.292V    14.9mA  COMMS         NONE
      65    21.2C    17.7C   -58.0C   7.485V    13.1mA  SCIENCE       NONE
      66    19.9C    21.0C    11.5C   7.418V    11.3mA  THERMAL       TIMING_SKEW
      67    19.8C    19.3C   -48.9C   7.340V    14.4mA  SCIENCE       TIMING_SKEW
      68    26.2C    15.7C   -26.6C   7.450V    15.6mA  COMMS         NONE
      69    22.4C    22.3C   -32.4C   7.318V    16.2mA  THERMAL       NONE
      70    20.9C    19.3C    15.5C   7.206V    18.4mA  SCIENCE       CURRENT_WARN
      71    21.7C    20.2C    23.6C   7.436V    18.3mA  ATTITUDE      NONE
      72    14.9C    22.0C   -56.1C   7.266V    12.6mA  SAFE          NONE
      73    21.6C    20.8C   -15.3C   7.335V    15.7mA  THERMAL       TEMP_WARN|SENSOR_DRIFT
      74    20.0C    19.6C   -49.3C   7.473V    15.0mA  UNK(48)       VOLTAGE_WARN|TIMING_SKEW|SENSOR_DRIFT|WATCHDOG_RESET|ANOMALY  ← ANOMALY
      75    23.4C    17.1C    69.2C   7.423V    11.2mA  UNK(109)      TEMP_WARN|ANOMALY  ← ANOMALY
      76    22.9C    19.6C    -2.8C   7.344V    15.6mA  ATTITUDE      NONE
      77    20.9C    19.0C   -34.9C   7.404V     6.3mA  POWER         NONE
      78    20.5C    17.6C    35.6C   7.341V    15.5mA  UNK(52)       VOLTAGE_WARN|CURRENT_WARN|COMM_DROP|TIMING_SKEW|SENSOR_DRIFT|ANOMALY  ← ANOMALY
      79    24.1C    20.2C   -45.8C   7.343V    15.4mA  UNK(108)      ANOMALY  ← ANOMALY
      80    24.4C    16.0C    91.1C   7.242V    16.9mA  POWER         NONE
      81    18.5C    18.4C   123.5C   7.291V    14.2mA  NOMINAL       TEMP_WARN|SENSOR_DRIFT
      82    20.4C    14.0C   -34.6C   7.407V    13.1mA  UNK(121)      TEMP_WARN|VOLTAGE_WARN|COMM_DROP|TIMING_SKEW|SENSOR_DRIFT|ANOMALY  ← ANOMALY
      83    24.3C    21.6C    41.6C   7.477V    18.6mA  UNK(125)      VOLTAGE_WARN|CURRENT_WARN|ANOMALY  ← ANOMALY
      84    20.7C    17.6C   -89.6C   7.359V    18.6mA  ATTITUDE      CURRENT_WARN
      85    17.2C    17.2C    71.4C   7.301V    13.1mA  SCIENCE       NONE
      86    21.6C    21.4C    24.2C   7.395V    18.0mA  SAFE          NONE
      87    22.1C    18.3C    -1.9C   7.457V    12.4mA  THERMAL       NONE
      88    19.5C    18.1C   -49.6C   7.525V    21.7mA  DIAGNOSTIC    NONE

[*] ANOMALY packets: 29

[+] FLAG: STARPWN{h0us3k33p1ng_4n0m4ly}
```

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
