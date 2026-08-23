# Oversized Downlink

| | |
|---|---|
| **Category** | Misc |
| **Points** | 450 |
| **Solves** | 178 |

## Description

You've been tasked to triage another SIGINT anomaly. A satellite downlinked what was supposed to be a 256x256 thumbnail of Earth limb imagery, but the on-bus bandwidth telemetry shows it was larger than a normal thumbnail of this size should be.

What's going on here?

**Attachments:** `downlink.png`

![Attachments](./challenges/downlink.png)

## Solution

### Steps

**1. Notice the size anomaly**

The image is 256×256 pixels — a standard thumbnail size — but the file is larger than expected. This hints that extra data has been hidden inside the image without changing its visible dimensions.

**2. Identify the steganography method**

The hidden data is embedded in the **LSB (Least Significant Bit) of the R channel** of each pixel. Since only the lowest bit of red is modified, the visual change is imperceptible.

**3. Extract the LSB of the R channel**

Iterate over every pixel in row-major order (left to right, top to bottom) and collect bit 0 of each red value into a bit string.

**4. Reconstruct the hidden bytes**

Group the extracted bits into 8-bit chunks and decode as ASCII. The flag appears near the start of the extracted data.

```bash
python3 solve.py downlink.png
```

Result:

```text
[+] R-channel LSB extraction complete!

--- Beginning of extracted data ---
*STARPWN{lsb_st3g0_1n_th3_d0wnl1nk_ch4nnel}ÿàÿãÿÿÿR©ÿø¥jªÕUUÿs9þ«U?ÃÇÿÿÿ1ÆÛ6fIãÇãUU?þlÀVªÌÙÿÀÿàãmUZc1Ìà?ÕZàðZÖÖµÇRÖà??ÀÎ8ÿÿ$ÙÁÖðø¥µjcªª<86ÛcU*ÀsKÁÿÀªªÉd*U8ãfl1I-Ã1ÇIxx|<%´Uÿÿ--Km[msqf3pãsãÿÿÛmÌ9¤¶ÌÉi$µ*3ç9Íø>ã9Æ8IªUm´sV«I6ªªqÇÎgÿl
----------------------------

[!] Flag found: STARPWN{lsb_st3g0_1n_th3_d0wnl1nk_ch4nnel}
```

### Exploit Code

```python
from PIL import Image
import re

def extract_lsb_r_channel(image_path):
    img = Image.open(image_path).convert("RGB")
    bits = ""
    for y in range(img.height):
        for x in range(img.width):
            r, _, _ = img.getpixel((x, y))
            bits += str(r & 1)

    text = "".join(chr(int(bits[i:i+8], 2)) for i in range(0, len(bits)-7, 8))

    match = re.search(r'STARPWN\{.*?\}', text)
    if match:
        print(f"FLAG: {match.group(0)}")

if __name__ == "__main__":
    extract_lsb_r_channel("downlink.png")
```

## Flag

```
STARPWN{lsb_st3g0_1n_th3_d0wnl1nk_ch4nnel}
```
