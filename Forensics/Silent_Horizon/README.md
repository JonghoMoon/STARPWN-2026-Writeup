# Silent Horizon

| | |
|---|---|
| **Category** | Forensics |
| **Points** | 500 |
| **Solves** | 25 |

## Description

You've been assigned to review a centuries old case. Apparently this was the beginning of a line of malware that is still damaging satellites to this day, go figure.

We've collected everything we could find in the link below. The STK Viewer is an .EXE, it only runs on Windows.

**Flag format:** `STARPWN{450:SAT12XXSAT11XXSAT13XXSAT12XX!}`

**Example:** `STARPWN{450:SAT1908SAT1408SAT1207SAT11607!}`

**Attachments:** `SilentHorizonConstellation.vdf`, `GCS1.txt` ~ `GCS4.txt`, `Ground Station Infection Times.txt`

## Solution

### Steps

**1. Parse infection times**

The `Ground Station Infection Times.txt` file records when each Ground Control Station (GCS) was infected:

| GCS | Infection Time |
|-----|---------------|
| GCS1 | 24 Apr 2026 20:16:20 |
| GCS2 | 24 Apr 2026 20:25:30 |
| GCS3 | 24 Apr 2026 20:52:30 |
| GCS4 | 24 Apr 2026 23:18:50 |

Only events within the 4-hour analysis window (2026-04-24 20:00 – 2026-04-25 00:00) are considered.

**2. Parse STK access reports**

Each `GCS{N}.txt` file is a System Tool Kit (STK) access report listing the time windows during which each GCS had a communication link with each satellite.

**3. Find simultaneously connected satellites at each infection time**

For each GCS infection time, identify all satellites that were within an access window at that exact moment:

| GCS | Simultaneous Satellites |
|-----|------------------------|
| GCS1 @ 20:16:20 | SAT1212, SAT1211 (2 satellites) |
| GCS2 @ 20:25:30 | SAT1304, SAT1303 (2 satellites) |
| GCS3 @ 20:52:30 | SAT1111 (1 satellite) |
| GCS4 @ 23:18:50 | SAT1208, SAT1307, SAT1108, SAT1207 **(4 satellites)** |

**4. Select the event with exactly 4 simultaneous accesses**

Only GCS4's infection event results in exactly 4 satellites connected simultaneously — these are the infected satellites.

**5. Order satellites by flag slot prefix**

The flag format specifies the slot order `12, 11, 13, 12` (the first two digits of each satellite ID). Sort satellites within each prefix group by access start time and fill the slots:

| Slot | Prefix | Selected |
|------|--------|----------|
| 1 | 12 | SAT1208 |
| 2 | 11 | SAT1108 |
| 3 | 13 | SAT1307 |
| 4 | 12 | SAT1207 |

### Exploit Code

```python
#!/usr/bin/env python3
"""
Usage:
    python3 solve_silent_horizon.py [--directory DIR]
"""
# (see full solve_silent_horizon.py for complete implementation)
# Key logic summary:

# 1. Parse infection times from "Ground Station Infection Times.txt"
# 2. For each GCS, parse GCS{N}.txt STK access report
# 3. Find satellites with active access window at the infection time
# 4. Select the GCS with exactly 4 simultaneous satellite accesses
# 5. Order satellites by prefix slots [12, 11, 13, 12]
# 6. Build flag: STARPWN{450:SAT1208SAT1108SAT1307SAT1207!}
```

## Flag

```
STARPWN{450:SAT1208SAT1108SAT1307SAT1207!}
```
