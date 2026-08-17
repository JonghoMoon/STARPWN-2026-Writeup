# Walk the False Line

| | |
|---|---|
| **Category** | Communication & RF |
| **Points** | 500 |
| **Solves** | 5 |

## Description

Based on your intel, Prismantir traced the enemy team to their hideout. This is a no-questions-asked contract, Ions will flow your way once the gig is closed, no need to know anything else. Apparently, they've been collecting some of our downed drones over time and made their own micro fleet to keep an eye out. Perfectly blended with our own. One such unit is currently holding position over the area. Your role is to make it check in at the recovery point long enough for the team to move in. We'll take it from there.

**RP: 36.124093, -115.275197 (+/- 100m)**

**Flag format:** `starpwn{[A-Za-z_]+}`

**Attachments:**
- `brdc1300.26n` — GPS broadcast ephemeris (RINEX nav)
- Web UI: `starpwn-147a501af55d-walk-the-false-line-0-0.chals.io`
- GPS RF input: `tcp:0.cloud.chals.io:<port>`
- Truth monitor: `tcp:0.cloud.chals.io:<port>`

## Solution

### Overview

This is a **GPS spoofing** challenge. The target drone is flying in autonomous mode, navigating via GPS. By injecting a fake GPS signal that gradually shifts the drone's perceived position toward the recovery point (RP), the drone's flight controller follows the spoofed coordinates without detecting the attack.

### Steps

**1. Identify active PRNs via Truth Monitor**

Connect to the Truth Monitor port to observe which GPS satellites (PRNs) the drone is currently tracking:

```bash
python3 truth_log.py <truth_port> -o truth_log.csv
```

Active PRNs in this session: **1, 2, 7, 14, 15, 17, 19, 20**

This PRNs are determined randomly for each server. If a new server is launched, you must read the "truth monitor" logs to match it.

**2. Generate a session-specific RINEX nav file**

Filter the provided `brdc1300.26n` to include only the active PRNs, producing `brdc1300_rx_prn_1_2_7_14_15_17_19_20.26n`. This ensures the simulated signal matches what the drone's receiver expects.

**3. Generate spoofed GPS IQ samples with gps-sdr-sim**

Use [gps-sdr-sim](https://github.com/osqzss/gps-sdr-sim) to generate a GPS L1 C/A baseband IQ file that simulates movement from the drone's current holding position to the recovery point:

```bash
# motion_hold15_nw700_hold120_600s.csv describes the spoofed trajectory:
# - Hold at current position for 15s
# - Move NW 700m over time
# - Hold at target for 120s
# Total: 600s scenario

gps-sdr-sim -e brdc1300_rx_prn_1_2_7_14_15_17_19_20.26n \
            -u motion_hold15_nw700_hold120_600s.csv \
            -s 2600000 \
            -b 16 \
            -o gpssim.bin
```

**4. Stream the IQ signal to the RF input port**

Send the generated IQ file to the challenge's RF input port in real time, with the correct SPWN1 header specifying the scenario start time and sample rate:

```bash
python3 stream_iq6.py gpssim.bin 0.cloud.chals.io <rf_port> \
    2026/05/10,12:16:35 2600000 10
```

The streamer sends:
```
SPWN1 scenario_t=2026/05/10,12:16:35 sample_rate=2600000\n
<raw signed int16 little-endian I/Q samples>
```

**5. Monitor the drone's position**

Watch the Web UI — the drone's GPS fix shifts from its holding position toward `36.124093, -115.275197`. The flight controller in AUTO mode follows the spoofed waypoint as if it were real.

**6. Flag appears at the recovery point**

Once the drone enters the ±100m radius around the RP, the ArduPilot console outputs the flag repeatedly:

```
starpwn{autonomous_until_someone_speaks_louder}
```

![GNU Radio](/Communication_and_RF/Walk_the_False_Line/images/flag.png)

### Key Files

| File | Description |
|------|-------------|
| `brdc1300.26n` | Original GPS broadcast ephemeris (provided) |
| `brdc1300_rx_prn_1_2_7_14_15_17_19_20.26n` | Filtered RINEX for active PRNs |
| `motion_hold15_nw700_hold120_600s.csv` | Spoofed trajectory CSV for gps-sdr-sim |
| `gpssim.bin` | Generated GPS L1 C/A IQ samples |
| `stream_iq6.py` | Real-time TCP streamer for IQ data |
| `truth_log.py` | Truth monitor client for PRN observation |

## Flag

```
starpwn{autonomous_until_someone_speaks_louder}
```
