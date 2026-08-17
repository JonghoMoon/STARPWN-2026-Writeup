# Nice day for fishing

| | |
|---|---|
| **Category** | Communication & RF |
| **Points** | 500 |
| **Solves** | 25 |

## Description

You wake up with one your alarms going off. Cortex has picked up some interesting signals coming out of Aquilon Mead, but no local sensors you can access remotely. You need to go there to collect the logs. Time for a fishing trip. Good thing you left that backdoor in Aeon's infra, their recon sat will come in handy for this one.

**Flag format:** `STARPWN.[a-zA-Z0-9_]+.`

**Attachments:** `nice_day_for_fishing.zip` (`aquilon_mead_sigint_node42.sigmf-data`, `.sigmf-meta`, `outputs_file_1.tiff`, `outputs_file_2.tiff`)

## Solution

### Steps

**1. Parse the SigMF capture**

The capture `aquilon_mead_sigint_node42.sigmf-data` is an RF recording in SigMF format from a SIGINT node at Aquilon Mead. The metadata file specifies the center frequency, sample rate, and data type.

**2. Demodulate AIS**

The signal contains AIS (Automatic Identification System) — the maritime vessel tracking protocol broadcast on VHF (161.975 MHz / 162.025 MHz). Demodulate GMSK and decode HDLC-framed NRZI AIS packets with CRC-16/X.25 validation.

Try multiple bit-alignment offsets (0–9) to maximize valid frame count:

```
offset=8: 419 valid frames  ← best
```

**Total CRC-valid AIS frames: 425**

**3. Parse the satellite TIFF imagery**

Two GeoTIFF frames (`outputs_file_1.tiff`, `outputs_file_2.tiff`) from Aeon's recon satellite cover the same area at different times. Detect moving objects by differencing the two frames — identifies **8 moving objects** in the imagery.

**4. Align RF and imagery timelines**

Cross-correlate AIS vessel positions with satellite-detected moving objects to find the best temporal alignment:

```
Best TIFF/RF alignment: 37.6s → 97.2s
```

**5. Classify MMSIs**

Match AIS-tracked vessels against satellite-confirmed moving objects. Vessels whose AIS-reported positions correspond to real satellite detections are **legitimate**; those that appear in AIS but have no satellite-visible counterpart are **phantom** (spoofed) transmitters:

| Type | MMSIs |
|------|-------|
| Legitimate | 211695738, 248917603, 271834956, 352781649, 419263587, 477328165, 563104892, 668195274 |
| Phantom | 305718642, 574902381, 731405982 |

**6. Extract the covert stream from phantom MMSIs**

The 3 phantom vessels are not real ships — they are used as a covert data channel. Decode the payload bytes hidden in their AIS transmissions:

```
Covert stream: b'\x00\x00\x00,#%#&)STARPWN.3_SP33DY_MMS1S.","\''
```

Search for the flag regex `STARPWN\.[A-Za-z0-9_]+\.` in the decoded stream to extract the flag.

### Exploit Code

```python
# Usage:
# python3 solve_nice_day_for_fishing.py \
#     aquilon_mead_sigint_node42.sigmf-data \
#     aquilon_mead_sigint_node42.sigmf-meta \
#     outputs_file_1.tiff \
#     outputs_file_2.tiff
#
# Dependencies: numpy scipy rasterio
#
# Pipeline:
# 1. GMSK demodulation + NRZI decode + HDLC frame extraction (AIS)
# 2. CRC-16/X.25 validation, try offsets 0-9, keep best
# 3. Rasterio: load TIFFs, detect moving objects via image differencing
# 4. Cross-correlate AIS positions with satellite detections -> time alignment
# 5. Hungarian algorithm (linear_sum_assignment) for MMSI-to-object matching
# 6. Phantom MMSIs -> covert stream -> regex search -> flag
```

## Flag

```
STARPWN.3_SP33DY_MMS1S.
```
