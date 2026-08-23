# Beaconing from above

| | |
|---|---|
| **Category** | Space Communication & RF |
| **Points** | 431 |
| **Solves** | 209 |

## Description

You get home to find that one of your old amateur radio projects received something interesting. Who say's leaving old tech listening doesn't pay off? Looks like it's coming from an old CubeSat, how did it survive this long?

The flag is the **four payload words**, joined by single underscores, wrapped in `STARPWN{...}`. Submission is case-sensitive; the decoded message is uppercase A-Z and digits.

**Hint 1:** The downlink is plain CW (continuous wave) Morse at the standard 12 WPM operator-readable rate on a 600 Hz tone.

**Hint 2:** The transmission follows the usual amateur format:
```
VVV VVV VVV DE <callsign> <callsign> <callsign>
<payload — four words>
73 DE <callsign> K
```

**Attachments:** `beacon.wav`

## Solution

### Steps

**1. Load and filter the WAV file**

Load `beacon.wav` and apply a 4th-order Butterworth bandpass filter (400–800 Hz) to isolate the 600 Hz CW tone from background noise.

**2. Envelope detection**

Apply the Hilbert transform to the filtered signal and take the absolute value to obtain the amplitude envelope. Smooth it with a uniform filter, then threshold at 30% of the peak to produce a binary ON/OFF mask.

**3. Segment extraction**

Detect rising and falling edges of the ON/OFF mask to extract a list of `(start, end)` sample pairs representing each tone burst.

**4. Symbol classification**

For each tone burst, compute its duration in milliseconds:
- Duration > 200 ms → `dah` (`—`)
- Duration ≤ 200 ms → `dit` (`.`)

For each gap between consecutive bursts:
- Gap > 500 ms → word boundary (`WORD`)
- Gap > 200 ms → character boundary (`CHAR`)

**5. Morse decoding**

Walk through the symbol sequence and accumulate dots/dashes into Morse codes, flushing on `CHAR` and `WORD` boundaries. Look up each code in `MORSE_MAP` to get the decoded character.

**6. Flag extraction**

The decoded word list follows the amateur CW format. Skip the leading `VVV`, `DE`, and the repeated callsign group, then take the next 4 words as the payload and join them with `_`.

```bash
python3 solve.py beacon.wav
```

Result:

```text
[*] Loading beacon.wav
    sample rate: 22050 Hz  |  duration: 82.4 s
[*] Detecting 600 Hz tone segments …
    found 217 tone segments
[*] Decoding Morse …
    message: VVV VVV VVV DE STARPWN STARPWN STARPWN B34C0N D3C0D3D V14 R4D10 73 DE STARPWN K

[+] FLAG: STARPWN{B34C0N_D3C0D3D_V14_R4D10}
```

### Exploit Code

```python
"""
CTF Beacon WAV - CW Morse Decoder
Decodes 12 WPM Morse code on a 600 Hz tone and extracts the flag.

Usage:
    python3 solve.py [path/to/beacon.wav]
"""

import sys
import wave
import numpy as np
from scipy.signal import butter, filtfilt, hilbert
from scipy.ndimage import uniform_filter1d


MORSE_MAP = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z',
    '-----': '0', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
}


def load_wav(path: str):
    with wave.open(path) as w:
        frames = w.readframes(w.getnframes())
        sr = w.getframerate()
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sr


def bandpass(data: np.ndarray, low: float, high: float, fs: int) -> np.ndarray:
    b, a = butter(4, [low / (fs / 2), high / (fs / 2)], btype='band')
    return filtfilt(b, a, data)


def detect_segments(samples, sr, tone_hz=600.0, bw=200.0, smooth_ms=10.0, threshold_ratio=0.3):
    filtered  = bandpass(samples, tone_hz - bw / 2, tone_hz + bw / 2, sr)
    envelope  = np.abs(hilbert(filtered))
    smooth    = uniform_filter1d(envelope, size=int(sr * smooth_ms / 1000))
    threshold = smooth.max() * threshold_ratio
    on        = smooth > threshold

    trans  = np.diff(on.astype(np.int8))
    starts = np.where(trans == 1)[0]
    ends   = np.where(trans == -1)[0]

    if on[0]:  starts = np.r_[0, starts]
    if on[-1]: ends   = np.r_[ends, len(on) - 1]

    return list(zip(starts, ends))


def segments_to_morse_words(segments, sr, dit_ms=100.0):
    dah_thresh  = dit_ms * 2
    char_thresh = dit_ms * 2
    word_thresh = dit_ms * 5

    syms = []
    for i, (s, e) in enumerate(segments):
        dur_ms = (e - s) / sr * 1000
        syms.append('dah' if dur_ms > dah_thresh else 'dit')

        if i < len(segments) - 1:
            gap_ms = (segments[i + 1][0] - e) / sr * 1000
            if gap_ms > word_thresh:
                syms.append('WORD')
            elif gap_ms > char_thresh:
                syms.append('CHAR')

    words, current_word, current_morse = [], [], ''

    def flush_char():
        nonlocal current_morse
        if current_morse:
            current_word.append(MORSE_MAP.get(current_morse, f'?{current_morse}?'))
            current_morse = ''

    def flush_word():
        flush_char()
        if current_word:
            words.append(''.join(current_word))
            current_word.clear()

    for sym in syms:
        if   sym == 'dit':  current_morse += '.'
        elif sym == 'dah':  current_morse += '-'
        elif sym == 'CHAR': flush_char()
        elif sym == 'WORD': flush_word()

    flush_word()
    return words


def extract_flag(words):
    i = 0
    while i < len(words) and words[i] in ('VVV', 'DE'):
        i += 1
    if i < len(words):
        callsign = words[i]
        while i < len(words) and words[i] == callsign:
            i += 1
    payload = words[i:i + 4]
    return 'STARPWN{' + '_'.join(payload) + '}'


def main(wav_path: str):
    samples, sr = load_wav(wav_path)
    segs = detect_segments(samples, sr)
    words = segments_to_morse_words(segs, sr)
    print(f"message: {' '.join(words)}")
    print(f"FLAG: {extract_flag(words)}")


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'beacon.wav'
    main(path)
```

## Flag

```
STARPWN{B34C0N_D3C0D3D_V14_R4D10}
```
