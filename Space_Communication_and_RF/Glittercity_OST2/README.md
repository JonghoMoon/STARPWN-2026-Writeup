# Glittercity OST2

| | |
|---|---|
| **Category** | Space Communication & RF |
| **Points** | 500 |
| **Solves** | 17 |

## Description

The grid goes dark.

Before shutdown, you swept the final useful arc over the Mojave just below one meter. The dish was tracking a dead machinery that once watched the whole planet, now drifting as one of the largest ghosts in orbit.

The receiver came back. Dead-Eye calling. Trying to reach back home.

Three fractured calls make one. It has forgotten letters, now it speaks in lines. Burn away the repeating veil forged from its number, high byte first.

Find the ghost. Recover the message.

**Attachments:** `Glittercity-OST2.mp3`

## Solution

### Steps

**1. Convert the MP3 to WAV and isolate the stereo difference channel**

Convert the MP3 to 48 kHz stereo PCM:

```bash
ffmpeg -i Glittercity-OST2.mp3 -ar 48000 -ac 2 ost2.wav
```

The hidden transmissions are most clearly visible in the stereo difference channel. Extract it as a mono WAV:

```bash
ffmpeg -i ost2.wav \
    -filter_complex "pan=mono|c0=0.5*c0-0.5*c1" \
    -ar 48000 \
    side.wav
```

---

**2. Decode the ground-calibration transmission**

Before the three Dead-Eye calls, there is a separate 2-FSK transmission around the 15-second mark.

![Flag](/Space_Communication_and_RF/Glittercity_OST2/images/audacity.png)

This signal acts as a known-good demodulation reference. Analysis gives:

```text
Sample rate        : 48000 Hz
Baud rate          : 300
Samples/symbol     : 160
Estimated tones    : ~10212.5 / 12212.5 Hz
Tone mapping       : low tone = 1, high tone = 0
Framing            : HDLC
FCS                 : CRC-16/X-25
```

The calibration signal contains repeated HDLC frames. After locating `0x7E` flags, removing HDLC bit stuffing, and validating the FCS, eight identical CRC-valid frames are recovered:

```text
CHANDELIER-7
STATUS=GROUND CALIBRATION
```

Example decoder output:

```text
[*] Sample rate        : 48000 Hz
[*] Baud rate          : 300.0
[*] Samples/symbol     : 160
[*] Estimated tones    : 10212.52 / 12212.52 Hz
[*] Symbol phase       : 50 samples
[*] Tone mapping       : low=1, high=0
[*] HDLC flags found   : 167
[+] CRC-valid frames   : 8
[+] Frame 01: bits 420..757, destuff 329 -> 328 bits (removed 1),
    FCS received=0x7E95, calculated=0x7E95 [OK]
...
[+] Unique payloads    : 1

--- Payload 1 ---
CHANDELIER-7
STATUS=GROUND CALIBRATION
```

This calibration transmission is important because it establishes the physical-layer parameters and, in particular, the FSK polarity used later for the Dead-Eye transmissions.

It also links OST2 back to OST1, where `CHANDELIER-7` appeared together with its TLE.

---

**3. Identify and extract the three Dead-Eye calls**

After the calibration signal, three separate Doppler-shifted 2-FSK transmissions appear later in the recording.

Extract them from `side.wav` with a small amount of padding:

```bash
ffmpeg -i side.wav -ss 41.4   -t 5.4 call1.wav
ffmpeg -i side.wav -ss 88.0   -t 5.4 call2.wav
ffmpeg -i side.wav -ss 134.65 -t 5.4 call3.wav
```

The three calls carry the same frame, but different portions of each reception are degraded. This corresponds directly to the challenge hint:

> Three fractured calls make one.

---

**4. Demodulate each call with GNU Radio**

Use GNU Radio Companion with the `gr-satellites` **AFSK Demodulator**.

A minimal flowgraph is:

```text
Wav File Source
      |
      v
Throttle
      |
      v
AFSK Demodulator
      +----> QT GUI Time Sink
      |
      +----> File Sink
```

Recommended settings:

```text
Sample rate : 48000
Baudrate    : 300
Deviation   : -1000 Hz
IQ input    : False
```

The negative deviation preserves the polarity established by the ground-calibration transmission:

```text
low tone  = 1
high tone = 0
```

Use an AF carrier appropriate for each Doppler-shifted call:

```text
Call 1 : ~14000 Hz
Call 2 : ~11080 Hz
Call 3 : ~8100 Hz
```

For Call 2, nearby values such as `11040`, `11060`, and `11080` Hz can be tested; `11080 Hz` produced a clean synchronization result in this solve.

The GNU Radio flowgraph outputs normalized float soft symbols rather than immediately forcing every symbol to `0` or `1`.

For example, Call 1 yields:

```text
preamble start symbol : 101
body start symbol     : 165
ASM errors            : 0
preamble errors       : 0
```

and begins with:

```text
1a cf fc 1d 00 9f d9 fd 11 1d 56 08 42 76 90 d5
```

The first four bytes are the CCSDS Attached Sync Marker:

```text
1A CF FC 1D
```

![GNU Radio](/Space_Communication_and_RF/Glittercity_OST2/images/gnu_radio_g2.png)

---

**5. Soft-combine the three demodulated streams**

Align the three `.soft` streams using the alternating 64-symbol preamble and the `1A CF FC 1D` ASM.

Normalize the amplitudes of the three soft streams and sum them symbol-by-symbol:

```python
soft_combined = soft1 + soft2 + soft3
bit = 1 if soft_combined > 0 else 0
```

This is more robust than hard majority voting. In a damaged section, the affected call produces soft values closer to zero, so the cleaner receptions dominate naturally.

As a validation step, explicitly masking the large degraded sections before summing gives exactly the same final 1336-bit result:

```text
difference = 0 / 1336 bits
```

The resulting frame is 167 bytes and has the following structure:

```text
1A CF FC 1D | 00 9F | [160-byte ciphertext] | 45
^^^^^^^^^^^   ^^^^^                            ^^
CCSDS ASM     length - 1                       CRC-8/DVB-S2
```

The two-byte length field is big-endian:

```text
0x009F + 1 = 160 bytes
```

which matches the ciphertext length exactly.

---

**6. Find the ghost — ENVISAT**

The challenge description points to **ENVISAT**, the defunct ESA Earth-observation satellite that lost contact in 2012 and remains one of the largest uncontrolled spacecraft in orbit.

Its NORAD catalog number is:

```text
27386
```

which is:

```text
0x6AFA
```

The hint:

> forged from its number, high byte first

therefore gives the repeating byte sequence:

```text
6A FA 6A FA 6A FA ...
```

---

**7. Burn away the repeating veil**

Apply the repeating XOR key to the **160-byte ciphertext only**:

```python
KEY = bytes.fromhex("6AFA")

plaintext = bytes(
    b ^ KEY[i % len(KEY)]
    for i, b in enumerate(ciphertext)
)
```

Do not include the ASM or the two-byte length field in the XOR stream.

Validate the decrypted payload with CRC-8/DVB-S2:

```text
Received CRC   : 0x45
Calculated CRC : 0x45
Result         : OK
```

This confirms both the reconstructed frame and the XOR alignment.

---

**8. Render the line-oriented message**

The first two decrypted bytes are:

```text
B3 07
```

which decode to:

```text
width  = 0xB3 = 179
height = 0x07 = 7
```

This explains the challenge hint:

> It has forgotten letters, now it speaks in lines.

The remaining bytes contain an MSB-first packed monochrome bitmap. Interpret the first:

```text
179 × 7 = 1253 bits
```

as seven scan lines and render them as a PBM or PNG image.

The resulting image reads:

```text
STARPWN{THIS_WAS_OFF_TOO_MUCH}
```

## Key Files

| File | Description |
|------|-------------|
| `ost2.wav` | Full 48 kHz stereo WAV converted from the MP3 |
| `side.wav` | Stereo difference channel containing the hidden FSK transmissions |
| `ground_calibration_side.wav` | Extracted CHANDELIER-7 calibration transmission |
| `call1.wav` / `call2.wav` / `call3.wav` | Extracted Dead-Eye transmissions |
| `call1.soft` / `call2.soft` / `call3.soft` | GNU Radio AFSK soft-symbol outputs |
| `soft_sum.bin` | 167-byte frame recovered by soft combining |
| `dead_eye_plain_160.bin` | Decrypted 160-byte payload |
| `dead_eye_message.pbm` | Reconstructed 179×7 monochrome bitmap |
| `g2.grc` / `g2.py` | GNU Radio flowgraph for AFSK demodulation |
| `decode_dead_eye.py` | Frame parser, CRC checker, XOR decoder, and bitmap renderer |

## Exploit Code

```python
#!/usr/bin/env python3
"""
Usage:
    python3 decode_dead_eye.py soft_sum.bin
"""

from pathlib import Path

ASM = bytes.fromhex("1ACFFC1D")
KEY = bytes.fromhex("6AFA")


def crc8_dvb_s2(data: bytes) -> int:
    crc: int = 0

    for byte_value in data:
        crc ^= int(byte_value)

        for _ in range(8):
            if (crc & 0x80) != 0:
                crc = ((crc << 1) ^ 0xD5) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    return int(crc)


def repeating_xor(data: bytes, key: bytes) -> bytes:
    return bytes(
        int(byte_value) ^ int(key[index % len(key)])
        for index, byte_value in enumerate(data)
    )


def unpack_msb_bits(data: bytes) -> list[int]:
    bits: list[int] = []

    for byte_value in data:
        value: int = int(byte_value)

        for bit_index in range(7, -1, -1):
            bits.append((value >> bit_index) & 1)

    return bits


frame = Path("soft_sum.bin").read_bytes()

assert len(frame) == 167
assert frame[:4] == ASM

payload_length = int.from_bytes(
    frame[4:6],
    byteorder="big",
    signed=False,
) + 1

ciphertext = frame[6:-1]
received_crc = int(frame[-1])

assert len(ciphertext) == payload_length

plaintext = repeating_xor(ciphertext, KEY)

calculated_crc = crc8_dvb_s2(plaintext)
assert calculated_crc == received_crc, "CRC mismatch"

width = int(plaintext[0])
height = int(plaintext[1])

bits = unpack_msb_bits(plaintext[2:])
bits = bits[: width * height]

pbm = [
    "P1",
    f"{width} {height}",
]

for row in range(height):
    row_pixels: list[str] = []

    for column in range(width):
        pixel = int(bits[row * width + column])
        row_pixels.append("0" if pixel != 0 else "1")

    pbm.append(" ".join(row_pixels))

Path("dead_eye_message.pbm").write_text(
    "\n".join(pbm) + "\n",
    encoding="ascii",
)

print(f"Bitmap: {width}x{height}")
print("FLAG: STARPWN{THIS_WAS_OFF_TOO_MUCH}")
```

## Flag

![Flag](/Space_Communication_and_RF/Glittercity_OST2/images/dead_eye_message.png)

```text
STARPWN{THIS_WAS_OFF_TOO_MUCH}
```
