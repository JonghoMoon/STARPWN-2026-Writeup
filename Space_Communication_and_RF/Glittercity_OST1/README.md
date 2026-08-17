# Glittercity OST1

| | |
|---|---|
| **Category** | Space Communication & RF |
| **Points** | 497 |
| **Solves** | 48 |

## Description

Wake up Glider. We've got a grid to light up.

Sipping on your midnight Synth'offee, you noticed something strange with the song in your brain. Is your GridLink glitching or is there something more to it? Good thing you managed to record it.

**Attachments:** `Glittercity-OST1.mp3`

## Solution

### Initial Analysis

Inspecting the MP3 ID3 tags with `xxd` reveals a TLE (Two-Line Element) embedded in the metadata under the `TXXX:comment` field:

```
TLE:
CHANDELIER-7
1 25544U 98067A   26207.41084145  .00010751  00000+0  20166-3 0  9995
2 25544  51.6317 105.9876 0006941 339.4731  20.5977 15.49181604577830
```

This hints that the signal relates to a satellite. The hidden data is not in the main audio but in the **side channel** (L − R), which carries a covert FSK transmission.

### Steps

**1. Decode MP3 to stereo PCM**

Use `ffmpeg` to decode the MP3 to 48 kHz signed 16-bit stereo PCM.

**2. Extract the side channel**

Compute the side channel as `(L − R) / 2`. The main music occupies the mid channel; the covert FSK signal is hidden in the difference.

**3. Track the Doppler frequency drift**

The FSK signal drifts in frequency over time due to Doppler shift from the satellite. Use a sliding FFT (window 32768, hop 8192) to track the lower FSK tone frequency. Score candidate bins by the geometric mean of the lower and upper tone magnitudes (separated by 2000 Hz). Apply Savitzky-Golay smoothing to get a clean Doppler trajectory from ~12300 Hz down to ~8100 Hz.

**4. Tune the symbol boundary offset**

The MP3 decoder may introduce a small sample offset. Scan offsets in the range [-80, +80] samples and choose the one that maximises the average matched-filter contrast across all symbols.

**5. Demodulate 300-baud BFSK**

For each of the 27,500 symbols, compute matched-filter energies at the low tone (`center − 1000 Hz`) and high tone (`center + 1000 Hz`). The low tone represents logical 1 and the high tone logical 0 (inverted convention).

**6. Parse HDLC frames**

Locate `0x7E` flag bytes (`01111110`) in the LSB-first bit stream, remove bit stuffing (zero after five consecutive ones), verify CRC-16/X-25, and extract the ASCII payload from each valid frame.

**7. Extract the flag**

Search the decoded ASCII payload for the `STARPWN{...}` pattern.

### Exploit Code

```python
#!/usr/bin/env python3
"""
Usage:
    python3 solve.py Glittercity-OST1.mp3

Dependencies: numpy, scipy, ffmpeg (CLI)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

SAMPLE_RATE        = 48_000
BAUD_RATE          = 300
SAMPLES_PER_SYMBOL = SAMPLE_RATE // BAUD_RATE
SIGNAL_START       = 15.0
SYMBOL_COUNT       = 27_500
TONE_DEVIATION_HZ  = 1_000.0
TONE_SEPARATION_HZ = 2.0 * TONE_DEVIATION_HZ


def decode_mp3_stereo(path):
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "2", "-ar", str(SAMPLE_RATE), "pipe:1"]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE)
    pcm = np.frombuffer(result.stdout, dtype="<i2").reshape((-1, 2)).astype(np.float64)
    return pcm / float(2**15)


def track_low_tone(side):
    fft_size = 32_768
    hop_size = 8_192
    window = np.hanning(fft_size)
    bin_hz = SAMPLE_RATE / fft_size
    tone_bin_offset = int(round(TONE_SEPARATION_HZ / bin_hz))
    start = int(round(SIGNAL_START * SAMPLE_RATE))
    end = start + SYMBOL_COUNT * SAMPLES_PER_SYMBOL

    times, freqs = [], []
    duration = SYMBOL_COUNT / BAUD_RATE
    for fs in range(max(0, start - fft_size // 2), min(len(side) - fft_size, end - fft_size // 2) + 1, hop_size):
        t = (fs + fft_size // 2) / SAMPLE_RATE
        nt = np.clip((t - SIGNAL_START) / duration, 0, 1)
        pred = 12300.0 + (8100.0 - 12300.0) * nt
        spec = np.abs(np.fft.rfft(side[fs:fs + fft_size] * window))
        lo = max(1, int(round((pred - 700) / bin_hz)))
        hi = min(len(spec) - tone_bin_offset - 2, int(round((pred + 700) / bin_hz)))
        cands = np.arange(lo, hi + 1)
        score = np.sqrt(spec[cands] * spec[cands + tone_bin_offset])
        best = cands[np.argmax(score)]
        # parabolic interpolation
        l, c, r = np.log(spec[best-1]+1e-30), np.log(spec[best]+1e-30), np.log(spec[best+1]+1e-30)
        d = l - 2*c + r
        offset = 0 if abs(d) < 1e-20 else 0.5 * (l - r) / d
        times.append(t); freqs.append((best + offset) * bin_hz)

    times, raw = np.array(times), np.array(freqs)
    smooth = signal.savgol_filter(raw, min(51, len(raw) if len(raw)%2==1 else len(raw)-1), 3)
    cleaned = raw.copy()
    cleaned[np.abs(raw - smooth) > 90] = smooth[np.abs(raw - smooth) > 90]
    return times, signal.savgol_filter(cleaned, min(41, len(cleaned) if len(cleaned)%2==1 else len(cleaned)-1), 3)


def demodulate_bits(side, start, times, low_hz):
    symbols = side[start:start + SYMBOL_COUNT * SAMPLES_PER_SYMBOL].reshape((SYMBOL_COUNT, SAMPLES_PER_SYMBOL))
    win = np.hanning(SAMPLES_PER_SYMBOL)
    idx = np.arange(SAMPLES_PER_SYMBOL, dtype=np.float64)
    mids = (start + np.arange(SYMBOL_COUNT) * SAMPLES_PER_SYMBOL + SAMPLES_PER_SYMBOL // 2) / SAMPLE_RATE
    center_hz = np.interp(mids, times, low_hz) + TONE_DEVIATION_HZ
    decisions = np.empty(SYMBOL_COUNT, dtype=np.uint8)
    for cs in range(0, SYMBOL_COUNT, 1024):
        ce = min(SYMBOL_COUNT, cs + 1024)
        chunk = symbols[cs:ce] * win
        cc = center_hz[cs:ce]
        lo_e = np.abs(np.sum(chunk * np.exp(-2j*np.pi*(cc[:,None]-TONE_DEVIATION_HZ)*idx/SAMPLE_RATE), axis=1))**2
        hi_e = np.abs(np.sum(chunk * np.exp(-2j*np.pi*(cc[:,None]+TONE_DEVIATION_HZ)*idx/SAMPLE_RATE), axis=1))**2
        decisions[cs:ce] = (hi_e > lo_e).astype(np.uint8)
    return decisions ^ 1


def crc16_x25(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return (crc ^ 0xFFFF) & 0xFFFF


def extract_frames(bits):
    flag = np.array([0,1,1,1,1,1,1,0], dtype=np.uint8)
    positions = [i for i in range(len(bits)-7) if np.array_equal(bits[i:i+8], flag)]
    frames = []
    for l, r in zip(positions, positions[1:]):
        stuffed = bits[l+8:r]
        out, ones, viols = [], 0, 0
        i = 0
        while i < len(stuffed):
            b = int(stuffed[i]); out.append(b)
            if b == 1:
                ones += 1
                if ones == 5:
                    if i+1 < len(stuffed) and stuffed[i+1] == 0: i += 1
                    else: viols += 1
                    ones = 0
            else: ones = 0
            i += 1
        if viols or len(out) < 24 or len(out) % 8 != 0: continue
        frame = np.packbits(np.array(out, dtype=np.uint8), bitorder='little').tobytes()
        if len(frame) >= 3 and int.from_bytes(frame[-2:], 'little') == crc16_x25(frame[:-2]):
            frames.append(frame)
    return frames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mp3", type=Path)
    args = parser.parse_args()

    stereo = decode_mp3_stereo(args.mp3)
    side = (stereo[:, 0] - stereo[:, 1]) * 0.5
    times, low_hz = track_low_tone(side)
    start = int(round(SIGNAL_START * SAMPLE_RATE))
    bits = demodulate_bits(side, start, times, low_hz)
    frames = extract_frames(bits)

    payloads = []
    for f in frames:
        p = f[:-2]
        if p not in payloads: payloads.append(p)

    combined = b"\n".join(payloads)
    match = re.search(rb"STARPWN\{[^}\r\n]+\}", combined)
    if match:
        print(f"FLAG: {match.group(0).decode()}")


if __name__ == "__main__":
    main()
```

## Flag

```
STARPWN{Syn7h_v1be$_fr0m_0rb1t}
```
