
# One to Rule Them All

| Item | Value |
|------|-------|
| Category | Communication & RF |
| Points | 499 |
| Solves | 32 |

## Description

Prismantir recovered a single enemy drone running **ArduPilot**. Although only one flight controller was captured, the swarm shares the same MAVLink2 signing key. Recover the signing key from the EEPROM dump, authenticate to the drone over MAVLink2, then use MAVLink FTP to retrieve the hidden image containing the flag.

**Flag format**

```text
starpwn{[A-Za-z_]+}
```

## Files

- `eeprom.bin` – 16 KiB ArduPilot EEPROM
- `GCS_Signing.cpp` – SigningKey structure
- `GCS_FTP.cpp/.h` – MAVLink FTP implementation
- `analyse_eeprom.py`
- `analyse_signing.py`
- `verify_key.py`
- `heartbeat.py`
- `find_png.py`
- `downloader.py`

---

# Solution

## 1. Identify the EEPROM

The dump begins with the `PA` magic used by ArduPilot AP_Param storage.

```bash
python3 analyse_eeprom.py eeprom.bin
```

The script also reports populated EEPROM regions and searches for the signing-key magic.

![EEPROM Layout](/Communication_and_RF/One_to_Rule_Them_All/images/01-eeprom-layout.png)

---

## 2. Recover the MAVLink2 signing key

`GCS_Signing.cpp` defines the persistent signing structure:

```cpp
struct SigningKey {
    uint32_t magic;
    uint64_t timestamp;
    uint8_t  secret_key[32];
};
```

The structure is identified using the magic value `0x3852FCD1`.

```bash
python3 analyse_signing.py eeprom.bin GCS_Signing.cpp
```

Recovered key:

```text
d4ee003d187614d9ffa24d20f58b448551c2cdc1e54cf42fc00bb86182249126
```

---

## 3. Verify the key

Before interacting with the drone, verify that the recovered key correctly authenticates signed MAVLink2 traffic.

```bash
python3 verify_key.py HOST PORT <KEYHEX>
```

Expected:

```text
[+] KEY VERIFIED
```

---

## 4. Enumerate the telemetry service

A simple heartbeat confirms that the connection and signing work correctly.

```bash
python3 heartbeat.py HOST PORT <KEYHEX>
```

---

## 5. Inspect the filesystem with MAVLink FTP

The drone exposes the ArduPilot MAVLink FTP service (`FILE_TRANSFER_PROTOCOL`).

List the filesystem:

```bash
python3 find_png.py
```

Result:

```text
/
 ├── eeprom.bin
 ├── DCIM
 │    └── flag.jpg
 └── terrain
```

---

## 6. Download the flag image

`downloader.py` implements the same packet format used by ArduPilot's `GCS_FTP.cpp`.

Protocol flow:

```text
ResetSessions
      ↓
OpenFileRO("DCIM/flag.jpg")
      ↓
ReadFile(offset=0, size=239)
      ↓
ReadFile(...)
      ↓
EOF
      ↓
TerminateSession
```

Run:

```bash
python3 downloader.py
```

Output:

```text
[+] File size : 40536 bytes
...
[+] Saved 40536 bytes to flag.jpg
```

---

## 7. Read the flag

Open `flag.jpg`.

![Recovered Flag](/Communication_and_RF/One_to_Rule_Them_All/scripts/flag.jpg)

The image contains the sentence:

> **machines never pledged to be allegiant**

Therefore the flag is

```text
starpwn{machines_never_pledged_to_be_allegiant}
```

---

# Attack Summary

```text
eeprom.bin
    │
    ├── Parse AP_Param EEPROM
    │
    ├── Locate SigningKey (0x3852FCD1)
    │
    ├── Extract 32-byte MAVLink2 signing key
    │
    ├── Verify with live signed telemetry
    │
    ├── Authenticate using MAVLink2 signing
    │
    ├── MAVLink FTP
    │      ├── LIST
    │      ├── OpenFileRO
    │      ├── ReadFile
    │      └── TerminateSession
    │
    └── Download DCIM/flag.jpg
            │
            └── Read flag
```
