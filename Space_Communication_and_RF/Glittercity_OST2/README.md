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

**1. Convert MP3 to WAV**

```bash
ffmpeg -i Glittercity-OST2.mp3 ost2.wav
```

**2. Identify and extract the three FSK calls**

Inspect the waveform to locate three separate 2-FSK transmissions. Crop each call into its own WAV file:

```
call2_11040.wav  (center 11040 Hz)
call2_11060.wav  (center 11060 Hz)
call2_11080.wav  (center 11080 Hz)
```

**3. Demodulate each call with GNU Radio**

Use the `gr-satellites` AFSK demodulator block at 300 baud, 48 kHz sample rate, with the appropriate AF carrier and −1000 Hz deviation for each call. The GNU Radio flowgraph (`g2.grc` / `g2.py`) outputs a float soft-symbol file (`.soft`) per call.

**4. Soft-combine the three demodulated streams**

Sum the three `.soft` files sample-by-sample to exploit diversity combining — each call carries the same frame but with different noise realizations. Threshold the result to recover a hard-decision bit stream and assemble the 167-byte frame:

```
1A CF FC 1D | 00 9F | [160-byte ciphertext] | 45
^^^^^^^^^^^   ^^^^^                            ^^
CCSDS ASM     length−1                         CRC-8/DVB-S2
```

**5. Find the ghost — ENVISAT**

The problem says *"Find the ghost"*. The ghost satellite is **ENVISAT** (NORAD 27386), a defunct ESA Earth-observation satellite that has been drifting uncontrolled since 2012. Its NORAD ID `27386` in hex is `0x6AFA`, which gives the 2-byte XOR key `6A FA`.

**6. Burn away the repeating veil**

Decrypt the 160-byte ciphertext with repeating-key XOR using `KEY = 6A FA`:

```python
plaintext = bytes(b ^ KEY[i % 2] for i, b in enumerate(ciphertext))
```

Verify with CRC-8/DVB-S2: received `0x45`, calculated `0x45` → OK.

**7. Render the bitmap**

The first two plaintext bytes give width (`0xB3` = 179) and height (`0x07` = 7). The remaining bytes are a packed MSB-first monochrome bitmap. Render to PBM and read the flag.

### Key Files

| File | Description |
|------|-------------|
| `ost2.wav` | Full WAV converted from MP3 |
| `call2_11040.soft` | GNU Radio soft output, call 1 |
| `call2_11060.soft` | GNU Radio soft output, call 2 |
| `call2_11080.soft` | GNU Radio soft output, call 3 |
| `dead_eye_plain_160.bin` | Decrypted 160-byte payload |
| `dead_eye_message.pbm` | Rendered bitmap containing the flag |
| `g2.grc` / `g2.py` | GNU Radio flowgraph for demodulation |
| `decode_dead_eye.py` | Frame parser and XOR decoder |

### Exploit Code

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
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0xD5) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def repeating_xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def unpack_msb_bits(data: bytes) -> list[int]:
    return [(b >> (7 - i)) & 1 for b in data for i in range(8)]


frame = Path("soft_sum.bin").read_bytes()
assert len(frame) == 167 and frame[:4] == ASM

payload_length = int.from_bytes(frame[4:6], "big") + 1
ciphertext = frame[6:-1]
received_crc = frame[-1]

plaintext = repeating_xor(ciphertext, KEY)
assert crc8_dvb_s2(plaintext) == received_crc, "CRC mismatch"

width, height = plaintext[0], plaintext[1]
bits = unpack_msb_bits(plaintext[2:])[:width * height]

pbm = ["P1", f"{width} {height}"]
for row in range(height):
    pbm.append(" ".join("0" if bits[row * width + col] else "1" for col in range(width)))

Path("dead_eye_message.pbm").write_text("\n".join(pbm) + "\n")
print(f"Bitmap: {width}x{height}")
print("FLAG: STARPWN{THIS_WAS_OFF_TOO_MUCH}")
```

## Flag

```
STARPWN{THIS_WAS_OFF_TOO_MUCH}
```
