# DEAD//LIGHT

| | |
|---|---|
| **Category** | Misc |
| **Points** | 500 |
| **Solves** | 25 |

## Description

Umbra has a new mission for you, and the Ion$ tag already tells you it's going to be a wild ride.

The Khepri Array photographed something after its transmitter was already gone. Engineering calls it sensor persistence. Navigation calls it impossible. The night shift stopped giving them names when the copies began arriving. Twelve guide-lights were mounted around the missing payload. Their factory coordinates survived in the archive. Their positions in the photograph did not. The center of the frame looks empty but that does not mean nothing came through. Your goal is to recover the Khepri message. At least their optics team left you some notes before dropping this on your:

> Never let all three ghosts vote on the same pixel. The ones travelling clockwise paid a different price.

**Attachments:** `deadlight-preview.png`

![Challenges](/Misc/DEAD_LIGHT/challenges/deadlight-preview.png)

## Solution

### Steps

**1. Convert the image to polar coordinates**

The payload text is hidden in the accretion disk around the black hole. Apply a polar transform centered at `(512, 506)` with radius range `[220, 460]` to unwrap the ring into a flat 2048×360 image (`01_polar.png`).

![Polar](/Misc/DEAD_LIGHT/images/01_polar.png)

**2. Identify the 36 guide-lights manually**

The polar image contains three overlapping "ghost" copies of the same message, each framed by 12 guide-lights. AI-assisted detection fails to reliably locate all lights, so the 36 guide-light pixel coordinates are confirmed manually by inspecting `polar_r220_460_3x.png`.

![Guide-Lights](/Misc/DEAD_LIGHT/images/polar_r220_460_3x.png)

**3. Extract three ghost images via ruled warp**

Using the confirmed guide-light coordinates for each ghost (A, B, C), apply a ruled warp — bilinearly interpolating between the top and bottom rows of 6 lights — to rectify each ghost into a flat 1500×300 output. Ghost C crosses the polar seam, so the polar image is duplicated horizontally before warping.

**4. Correct ghost B orientation**

Ghosts A and C share the same reading direction, but ghost B is mirrored. Flip ghost B horizontally (`03_raw_B_flipx.png`) so all three are aligned for comparison.

**5. Enhance contrast for readability**

Apply CLAHE (contrast-limited adaptive histogram equalization) followed by unsharp masking to each rectified ghost to improve legibility of the embedded text.

**6. Read the flag from ghost C**

Ghost C (`04_raw_C.png` / `07_C_enhanced.png`) yields the clearest rendering of the message. Reading across the two lines gives the flag.

![Raw_C](/Misc/DEAD_LIGHT/images/04_raw_C.png)

![C-enhanced](/Misc/DEAD_LIGHT/images/07_C_enhanced.png)


### Images

| File | Description |
|------|-------------|
| `deadlight-preview.png` | Original challenge image |
| `01_polar.png` | Polar-unwrapped ring |
| `polar_r220_460_3x.png` | Polar image with 36 guide-lights marked |
| `02_raw_A.png` | Ghost A rectified |
| `03_raw_B_flipx.png` | Ghost B rectified and flipped |
| `04_raw_C.png` | Ghost C rectified |
| `05_A_enhanced.png` | Ghost A enhanced |
| `06_B_flipx_enhanced.png` | Ghost B enhanced |
| `07_C_enhanced.png` | Ghost C enhanced |
| `08_compare_ABC.png` | All three ghosts side-by-side |

### Exploit Code

```python
#!/usr/bin/env python3
"""
Usage:
    python3 solve.py deadlight-preview.png
"""

import argparse
from pathlib import Path
import cv2
import numpy as np

A_GUIDES = np.array([
    [1437.078, 15.595], [1316.639, 8.566], [1201.391, 15.945],
    [1072.591, 27.870], [919.432, 32.442], [934.531, 53.771],
    [966.670, 81.714], [1015.349, 98.619], [1212.500, 74.031],
    [1407.381, 45.898], [1582.626, 41.473], [1548.295, 30.174],
], dtype=np.float32)

B_GUIDES = np.array([
    [495.782, 198.459], [606.333, 172.703], [825.862, 189.634],
    [1004.292, 204.396], [1157.990, 203.438], [1154.832, 223.993],
    [1131.464, 247.446], [1092.362, 261.569], [905.511, 260.489],
    [683.737, 237.686], [417.151, 247.866], [417.371, 232.113],
], dtype=np.float32)

C_GUIDES = np.array([
    [1634.184, 110.695], [1729.495, 95.495], [1883.240, 105.058],
    [2040.576, 116.495], [2215.670, 109.348], [2227.177, 125.496],
    [2195.398, 147.945], [2136.575, 168.743], [1924.473, 165.847],
    [1710.973, 145.747], [1497.349, 149.946], [1534.848, 133.964],
], dtype=np.float32)


def make_polar(image_bgr):
    W, H = 2048, 360
    cx, cy = 512.0, 506.0
    r_min, r_max = 220.0, 460.0
    x = np.arange(W, dtype=np.float32)[None, :]
    y = np.arange(H, dtype=np.float32)[:, None]
    r = r_min + (r_max - r_min) * y / H
    theta = -2.0 * np.pi * x / W
    map_x = (cx + r * np.cos(theta)).astype(np.float32)
    map_y = (cy + r * np.sin(theta)).astype(np.float32)
    return cv2.remap(image_bgr, map_x, map_y, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))


def ruled_warp(polar_bgr, guides, output_width=1500, output_height=300):
    top_ids    = [0, 1, 2, 3, 4, 5]
    bottom_ids = [11, 10, 9, 8, 7, 6]
    columns = np.linspace(0.0, float(output_width - 1), num=6, dtype=np.float32)
    map_x = np.zeros((output_height, output_width), dtype=np.float32)
    map_y = np.zeros((output_height, output_width), dtype=np.float32)
    vt = np.linspace(0.0, 1.0, num=output_height, dtype=np.float32)[:, None]

    for dx in range(output_width):
        si = int(max(0, min(4, np.searchsorted(columns, float(dx), side='right') - 1)))
        ht = (float(dx) - columns[si]) / max(1.0, columns[si + 1] - columns[si])
        top = ((1 - ht) * guides[top_ids[si]] + ht * guides[top_ids[si + 1]]).astype(np.float32)
        bot = ((1 - ht) * guides[bottom_ids[si]] + ht * guides[bottom_ids[si + 1]]).astype(np.float32)
        src = ((1 - vt) * top + vt * bot).astype(np.float32)
        map_x[:, dx] = src[:, 0]
        map_y[:, dx] = src[:, 1]

    polar_double = np.concatenate([polar_bgr, polar_bgr], axis=1)
    return cv2.remap(polar_double, map_x, map_y, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))


def enhance(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(gray)
    blur = cv2.GaussianBlur(contrast, (0, 0), sigmaX=1.0)
    return cv2.addWeighted(contrast, 1.6, blur, -0.6, 0.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--outdir", type=Path, default=Path("khepri_out"))
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(args.input), cv2.IMREAD_COLOR)
    polar = make_polar(img)

    raw_a = ruled_warp(polar, A_GUIDES)
    raw_b = cv2.flip(ruled_warp(polar, B_GUIDES), 1)
    raw_c = ruled_warp(polar, C_GUIDES)

    cv2.imwrite(str(args.outdir / "01_polar.png"), polar)
    cv2.imwrite(str(args.outdir / "02_raw_A.png"), raw_a)
    cv2.imwrite(str(args.outdir / "03_raw_B_flipx.png"), raw_b)
    cv2.imwrite(str(args.outdir / "04_raw_C.png"), raw_c)
    cv2.imwrite(str(args.outdir / "05_A_enhanced.png"), enhance(raw_a))
    cv2.imwrite(str(args.outdir / "06_B_flipx_enhanced.png"), enhance(raw_b))
    cv2.imwrite(str(args.outdir / "07_C_enhanced.png"), enhance(raw_c))

    print("[+] FLAG: STARPWN{DEAD_SIGN_RETURNS}")


if __name__ == "__main__":
    main()
```

## Flag

![Flag](/Misc/DEAD_LIGHT/images/09_compare_ABC_enhanced.png)

```
STARPWN{DEAD_SIGN_RETURNS}
```
