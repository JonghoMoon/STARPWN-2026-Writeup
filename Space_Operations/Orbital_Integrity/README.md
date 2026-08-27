# Orbital Integrity 

| | |
|---|---|
| **Category** | Space Operations |
| **Points** | 421 |
| **Solves** | 224 |

## Description

New briefing from Titan Corp, with some nice Ion$ to match it. Looks like a corrupted ground-station transmission left their TLE catalog with every line checksum replaced by `x`. The orbital elements themselves came through intact, but without valid checksums their tracking software refuses to accept the file and five satellites are drifting toward a comms blackout. Give them a hand will you?

**Flag format:** `STARPWN{<10 digits>}`

**Attachments:** `corrupted_tles.txt`

## Solution

### Steps

**1. Understand the TLE checksum algorithm**

Each TLE line ends with a single checksum digit. It is calculated by summing all digit characters in the line (excluding the last character) and adding 1 for each `-` sign. All other characters contribute 0. The final checksum is the sum modulo 10.

**2. Compute checksums for all 5 satellites**

Apply the checksum algorithm to Line 1 and Line 2 of each TLE:

| Satellite | Line 1 | Line 2 |
|-----------|--------|--------|
| ISS | 2 | 9 |
| HUBBLE | 1 | 1 |
| NOAA 19 | 5 | 6 |
| LANDSAT 9 | 5 | 9 |
| STARLINK | 3 | 6 |

**3. Concatenate the 10 checksum digits**

Reading the checksums left-to-right, top-to-bottom gives the 10-digit flag payload: `2911565936`.

### Exploit Code

```python
def calculate_tle_checksum(line):
    checksum = 0
    for char in line[:-1]:
        if char.isdigit():
            checksum += int(char)
        elif char == '-':
            checksum += 1
    return str(checksum % 10)

def main():
    filename = 'corrupted_tles.txt'
    name_mapping = {
        "ISS (ZARYA)": "ISS",
        "HUBBLE SPACE TELESCOPE": "HUBBLE",
        "NOAA 19": "NOAA 19",
        "LANDSAT 9": "LANDSAT 9",
        "STARLINK-31415": "STARLINK"
    }

    with open(filename, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    total = ""
    for i in range(0, len(lines), 3):
        raw_name = lines[i]
        line1, line2 = lines[i+1], lines[i+2]
        display_name = name_mapping.get(raw_name, raw_name)
        chk1 = calculate_tle_checksum(line1)
        chk2 = calculate_tle_checksum(line2)
        total += chk1 + chk2
        print(f"{display_name:<11}: {chk1} {chk2}")

    print(f"\nFLAG: STARPWN{{{total}}}")

if __name__ == "__main__":
    main()
```

## Flag

```
STARPWN{2911565936}
```
