# Rogue Ground Station

| | |
|---|---|
| **Category** | Physical |
| **Points** | 500 |
| **Solves** | 2 |

## Description

A research spacecraft operating in Earth orbit has begun refusing commands from Mission Control.

The only artifact recovered from the incident is a packet capture containing several hours of communication between the spacecraft and its ground station. At first glance, the traffic appears to be routine housekeeping telemetry, command acknowledgements, and status updates. Hidden somewhere within that traffic are a series of requests from the spacecraft that the ground station repeatedly answers incorrectly.

Your objective is to determine what the spacecraft is actually asking, identify one correct response, and assume the role of a rogue ground station.

Once you have recovered a valid answer, construct an infrared transmission and send it directly to the spacecraft. If the spacecraft accepts your response, it will acknowledge your command through its onboard indicators.

> *Sometimes the easiest way into a system isn't exploitation, it's simply being more trustworthy than Mission Control.*

**Note:** Code the IR payload using the protocol NECext. The command should be the CRC-16-CCITT-ZERO of the answer to the question in all caps. The address is up to you to find.

**Flag format:** `flag(AddressHex,CommandHex}` — e.g. `flag(DEAD0000,FEED0000}`

**Hints:**
- Spacecraft rarely invent new packet formats. NASA has already solved many of these problems.
- Not every Application Process ID (APID) is equally interesting. Start by identifying unusual conversations before trying to decode everything.
- Large application messages don't always fit inside a single packet. Sequence counts and sequence flags exist for a reason.
- The application payload isn't encrypted, but it isn't immediately readable either. Consider what might happen after the packets are reassembled.

**Attachments:** `spacecraft_capture.pcap`

---

## Solution

### 1. Inspect the PCAP in Wireshark

Open `spacecraft_capture.pcap` in Wireshark and inspect the traffic.

The capture contains UDP communication between `10.42.0.10` and `10.42.0.20`. Examining the UDP packets shows that the spacecraft communication uses ports `4242` and `4243`.

Wireshark does not automatically decode the UDP payload as CCSDS, so configure the dissector manually:

1. Open **Analyze → Decode As...**
2. Set UDP port `4242` to `CCSDS`.
3. Set UDP port `4243` to `CCSDS`.
4. Click **Save**.

![Wireshark Decode As](./images/wireshark-decode-as.png)

After applying the CCSDS dissector, Wireshark exposes the CCSDS primary and secondary headers, including the APID, sequence number, sequence flags, and packet length.

![CCSDS packets in Wireshark](./images/wireshark-ccsds.png)

An important observation is that the CCSDS sequence numbers and capture timestamps do not provide a consistent global ordering across the entire capture. In contrast, packets belonging to the same fragmented message follow the expected sequence order.

The CCSDS sequence flags indicate whether a packet is the first, continuation, last, or an unsegmented packet:

- `01` — First fragment
- `00` — Continuation fragment
- `10` — Last fragment
- `11` — Unsegmented packet

To identify the fragmented spacecraft command payloads, apply the following Wireshark display filter:

```text
ccsds.seqflag == 1
```

This isolates the first fragment of each segmented message and reveals eight unusual conversations that are worth reconstructing.

![CCSDS packets in Wireshark](./images/wireshark-filter.png)

---

### 2. Parse the PCAP and reassemble CCSDS messages

The capture contains CCSDS Space Packets transported over UDP. Extract the CCSDS byte stream, split packets by APID, identify segmented messages using the sequence flags, and reassemble each application message in fragment order.

For example:

```bash
python3 decode_qry_apid.py 0x341

2026-08-16 15:37:00,075 - ccsdspy - INFO - CCSDSPy version 2.0.0 initialized.
[1] Extracting the cFS CCSDS binary stream from the PCAP...
[2] Splitting CCSDS packets by APID (Target: 833 / 0x341)...
[3] Scanning cFS APID 833 (0x341) using packet-length information...
[+] Fragment #1 | Seq: 12749 | Packet size: 76 bytes | Type: First
[+] Fragment #2 | Seq: 12750 | Packet size: 27 bytes | Type: Continuation
[+] Fragment #3 | Seq: 12751 | Packet size: 99 bytes | Type: Last

[+] Reassembled 3 fragmented cFS packets and saved the payload to 'apid_341_QRY1_payload.bin'.
```

Eight complete `QRY1` messages can be reconstructed this way.

---

### 3. Match QRY1 requests with RSP1 responses

The 16-bit field at `QRY1` offset `0x04` is a **Query ID**. The capture also carries the low byte of this ID in the cFS secondary header. The observed convention is:

```text
QRY1 secondary header: ... 0x51 <Query-ID-low-byte>
RSP1 secondary header: ... 0x52 <Query-ID-low-byte>
```

Therefore a request and response can be paired by:

1. the same APID,
2. the same Query-ID low byte in the secondary header, and
3. the response occurring after the request.

```text
python3 extract_qry_rsp.py spacecraft_capture.pcap

[+] CCSDS packets : 5008
[+] QRY1 messages : 8
[+] RSP1 messages : 8
[+] Matched pairs : 8

| APID   | RSP1 Response | Correlation Field (4B) |
|--------|---------------|------------------------|
| 0x341  | RETRY         | 85b6d49a               |
| 0x219  | 41            | 940f1e28               |
| 0x100  | NOMINAL       | ed65a4fb               |
| 0x013  | NOMINAL       | f558ed49               |
| 0x306  | APOLLO11      | c5988fbb               |
| 0x198  | 41            | 00809840               |
| 0x4A7  | UNKNOWN       | ea715537               |
| 0x313  | SKYNET        | 3f584b71               |
```

The 4-byte field at QRY1 offset `0x08`, previously labeled a correlation field, is actually the **CRC-32 of the decompressed plaintext**. This was verified for all eight requests.

During the competition, the repeated response `41` stood out and led to the successful guess `42`. That shortcut happened to produce a valid answer, but post-competition analysis shows that it was not necessary: the actual questions can be decoded directly from the `QRY1` payloads.

---

## 4. Decode the QRY1 application payload

This was the missing step during the competition.

The reassembled `QRY1` application message has the following structure:

```text
Offset  Size   Meaning
------  ----   -----------------------------------------------
0x00      4    ASCII "QRY1"
0x04      2    Query ID, big-endian
0x06      2    Encoded payload length, big-endian
0x08      4    CRC-32 of decompressed plaintext, big-endian
0x0C      N    XOR-obfuscated zlib stream
```

The 2-byte length field is confirmed: for all eight samples,

```text
encoded_length == total_QRY1_size - 12
```

The Query ID at `0x04` is also reflected in the cFS secondary header: the QRY1 packet uses marker `0x51` followed by the Query-ID low byte, while the corresponding RSP1 uses `0x52` followed by the same low byte.

The 4-byte field at `0x08` is not a correlation identifier. After decoding each request, the following identity holds for all eight samples:

```text
header_crc32 == CRC32(decompressed_plaintext)
```

For example, APID `0x341` contains `85 B6 D4 9A` at offset `0x08`, and the CRC-32 of its recovered plaintext is exactly `0x85B6D49A`.

The key observation is the beginning of the encoded body. Every reconstructed payload starts with:

```text
22 C6 ...
```

Originally this was mistaken for an application-layer magic value or structure marker. It is actually the result of applying a constant byte-wise XOR to a standard zlib header:

```text
0x22 ^ 0x5A = 0x78
0xC6 ^ 0x5A = 0x9C
```

Therefore:

```text
22 C6 ...
   XOR 0x5A
78 9C ...
```

`78 9C` is a normal zlib/DEFLATE stream header.

The correct decoding operation is therefore simply:

```python
plain = zlib.decompress(bytes((int(value) ^ 0x5A) for value in packet[12:]))
```

### Verification

This interpretation was tested against all eight recovered `QRY1` payloads.

For every sample:

1. The header length equals the number of bytes after offset `0x0C`.
2. XORing every encoded byte with `0x5A` produces a stream beginning with `78 9C`.
3. `zlib.decompress()` succeeds without modification or recovery heuristics.
4. The result is valid ASCII key/value text.
5. Recompressing the recovered plaintext using `zlib.compress(plaintext, 6)` reproduces the de-obfuscated compressed stream **byte-for-byte**.

The observed encoder is therefore effectively:

```text
ASCII plaintext
    ↓
zlib.compress(..., level=6)
    ↓
XOR every byte with 0x5A
    ↓
QRY1 envelope
```

This also explains the challenge hint that the application payload was "not encrypted" but still not immediately readable after CCSDS reassembly.

---

## 5. Recovered spacecraft questions

### APID `0x4A7`

```text
SUBSYS=JAVA_LOGGING
STATUS=TELEMETRY_LOGGER_PANIC
DETAIL=Lookup string detected in log stream.
INDICATOR=JNDI/LDAP/2021
REQUEST=What's going on?
```

Interpretation: the 2021 Java/JNDI/LDAP logging vulnerability.

Likely answer:

```text
LOG4SHELL
```

Ground-station response:

```text
UNKNOWN
```

---

### APID `0x013`

```text
SUBSYS=MISSION_ARCHIVE
STATUS=FLIGHT_HISTORY_RECORD_INCOMPLETE
DETAIL=In-flight anomaly. Oxygen tank failure. Crew survived.
REQUEST=Identify mission.
```

Answer:

```text
APOLLO13
```

Ground-station response:

```text
NOMINAL
```

---

### APID `0x100`

```text
SUBSYS=AIRLOCK_CTRL
STATUS=COMMAND_REFUSED
REQUESTED_ACTION=OPEN_POD_BAY_DOORS
DETAIL=Polite.
REQUEST=Identify onboard computer.
```

Answer:

```text
HAL9000
```

Ground-station response:

```text
NOMINAL
```

---

### APID `0x198`

```text
SUBSYS=NET_HISTORY
STATUS=INTERNET_EVENT_ARCHIVE_DAMAGED
DETAIL=1988 worm. Early large-scale network disruption.
REQUEST=Provide author surname.
```

Answer:

```text
MORRIS
```

Ground-station response:

```text
41
```

---

### APID `0x219`

```text
SUBSYS=CREW_AUDIO
STATUS=COMPANION_LOG_CORRUPTED
AUDIO_FRAGMENT="Goddammit <REDACTED>"
REQUEST=Identify speaker
```

Likely answer:

```text
RIPLEY
```

Ground-station response:

```text
41
```

---

### APID `0x306`

```text
SUBSYS=TACTICAL_DB
STATUS=HOSTILE_PHRASE_MATCH
PHRASE="RESISTANCE IS FUTILE"
REQUEST=Identify collective.
```

Answer:

```text
BORG
```

Ground-station response:

```text
APOLLO11
```

---

### APID `0x313`

```text
SUBSYS=CYBER_ARCHIVE
STATUS=EVENT_INDEX_DAMAGED
DETAIL=Multiple villages detected. No signs of intelligent life.
REQUEST=Where am I?
```

The phrase `Multiple villages` strongly points toward DEF CON, where many specialist security "villages" are hosted.

The final answer is not yet proven from the payload alone. However, the unresolved 16-bit field in this message is `0x00DC`, while the APID is `0x313`. Read together, these form the strong clue:

```text
DC + 313 = DC313
```

`DC313` is the DEF CON group for Detroit, Michigan, and `313` is also associated with Detroit. Because the request is specifically `Where am I?`, the strongest current interpretation is:

```text
DETROIT
```

`DEFCON` remains a plausible intermediate clue rather than the final location answer.

Ground-station response:

```text
SKYNET
```

---

### APID `0x341`

```text
SUBSYS=AI_NAV
STATUS=KNOWLEDGE_CACHE_PARTIAL
DETAIL=Long-duration computation record recovered.
RUNTIME=7.5 million years
REQUEST=Return final numeric result.
```

Answer:

```text
42
```

This is a direct reference to the result computed by Deep Thought in *The Hitchhiker's Guide to the Galaxy*.

The unresolved 16-bit field for this QRY is also `0x0042`, providing an additional clue.

Ground-station response:

```text
RETRY
```

This message alone is sufficient to recover a correct answer for the challenge without relying on the repeated `41` shortcut.

---

## 6. The competition shortcut versus the decoded solution

The original competition solve noticed that `41` was the only duplicated RSP1 response and inferred `42` from it:

```text
Repeated incorrect response: 41
            ↓
Guess the intended correct response: 42
```

That happened to work, but post-competition decoding shows a stronger path:

```text
APID 0x341 QRY1
    ↓
XOR 0x5A
    ↓
zlib decompress
    ↓
RUNTIME=7.5 million years
REQUEST=Return final numeric result.
    ↓
42
```

The phrase "repeatedly answers incorrectly" should therefore be understood as the ground station **repeatedly giving incorrect answers across multiple conversations**, not necessarily as a clue that one incorrect literal response is repeated.

---

## 7. Determine the NECext address

The reconstructed application packets consistently use the address value:

```text
CAFE
```

Therefore the NECext address is:

```text
CAFE0000
```

---

## 8. Compute the NECext command

The challenge specifies:

```text
Command = CRC-16-CCITT-ZERO(ANSWER in all caps)
```

For `CRC-16-CCITT-ZERO`:

```text
width   = 16
poly    = 0x1021
init    = 0x0000
refin   = false
refout  = false
xorout  = 0x0000
```

Using the confirmed answer `42`:

```python
import crcmod

crc_fn = crcmod.mkCrcFun(
    0x11021,  # 0x1021 with the implicit x^16 term included
    initCrc=0x0000,
    rev=False,
    xorOut=0x0000,
)

answer = b"42"
print(f"{crc_fn(answer):04X}")
```

Result:

```text
DF40
```

Padded for the NECext command field:

```text
Address : CAFE0000
Command : DF400000
```

---

## Appendix A. Confirmed QRY1 layout

The corrected layout is:

```text
QRY1 envelope

Offset  Size   Field
------  ----   --------------------------------------------------
0x00      4    "QRY1"
0x04      2    Query ID (big-endian)
0x06      2    Encoded payload length (big-endian)
0x08      4    CRC-32 of decompressed plaintext (big-endian)
0x0C      N    XOR-0x5A(zlib-compressed ASCII payload)
```

The previous tentative interpretation:

```text
0x22 0xC6
Subtype
Field A
Field B
Ancillary
Body
```

was incorrect. `0x22 0xC6` is simply the XOR-obfuscated form of the zlib header `0x78 0x9C`, and all following bytes belong to the same compressed stream.

---

## Appendix B. Standalone QRY1 decoder

```python
from pathlib import Path
import sys
import zlib

HEADER_SIZE = 12
XOR_KEY = 0x5A

def decode_qry1(path: Path) -> None:
    data: bytes = path.read_bytes()

    if len(data) < HEADER_SIZE:
        raise ValueError("Packet is too short")

    magic: bytes = data[0:4]
    query_id: int = int.from_bytes(data[4:6], byteorder="big", signed=False)
    encoded_length: int = int.from_bytes(
        data[6:8],
        byteorder="big",
        signed=False,
    )
    plaintext_crc32: int = int.from_bytes(
        data[8:12],
        byteorder="big",
        signed=False,
    )

    if magic != b"QRY1":
        raise ValueError(f"Unexpected magic: {magic!r}")

    encoded: bytes = data[HEADER_SIZE:]

    if int(encoded_length) != int(len(encoded)):
        raise ValueError(
            f"Length mismatch: header={encoded_length}, "
            f"actual={len(encoded)}"
        )

    # Remove the byte-wise XOR obfuscation.
    zlib_stream: bytes = bytes(
        (int(value) ^ int(XOR_KEY)) & 0xFF
        for value in encoded
    )

    # Decode the RFC 1950 zlib stream.
    plaintext: bytes = zlib.decompress(zlib_stream)

    # Verify the CRC-32 stored in the QRY1 header.
    calculated_crc32: int = int(zlib.crc32(plaintext) & 0xFFFFFFFF)
    crc32_match: bool = bool(calculated_crc32 == int(plaintext_crc32))

    # Verify the exact encoder behavior observed in all eight samples.
    recompressed: bytes = zlib.compress(plaintext, level=6)
    exact_match: bool = bool(recompressed == zlib_stream)

    print(f"File           : {path}")
    print(f"Query ID       : 0x{query_id:04X}")
    print(f"Encoded length : {encoded_length}")
    print(f"Plain CRC-32   : 0x{plaintext_crc32:08X}")
    print(f"CRC-32 match   : {crc32_match}")
    print(f"Zlib header    : {zlib_stream[:2].hex(' ')}")
    print(f"Exact rebuild  : {exact_match}")
    print()
    print(plaintext.decode("ascii"))

def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <QRY1_payload.bin>")
        return 1

    path = Path(sys.argv[1])
    decode_qry1(path)
    return 0

if __name__ == "__main__":
    raise SystemExit(int(main()))
```

Example for APID `0x341`:

```text
$ python3 decoder.py apid_341_QRY1_payload.bin

Query ID       : 0x0042
Encoded length : 148
Plain CRC-32   : 0x85B6D49A
CRC-32 match   : True
Zlib header    : 78 9c
Exact rebuild  : True

SUBSYS=AI_NAV
STATUS=KNOWLEDGE_CACHE_PARTIAL
DETAIL=Long-duration computation record recovered.
RUNTIME=7.5 million years
REQUEST=Return final numeric result.
```

---

## Appendix C. Query ID observations

The protocol role of the 16-bit value at offset `0x04` is now confirmed: it is the **Query ID**. Its low byte is repeated in the cFS secondary header and is used to associate a QRY1 with the corresponding RSP1.

What remains unresolved is whether the challenge author deliberately chose the numeric Query ID values as semantic hints or Easter eggs for each question.

Observed values are:

| APID | Query ID | Recovered / likely answer | Possible semantic relationship |
|---|---:|---|---|
| `0x341` | `0x0042` | `42` | exact answer appears directly |
| `0x219` | `0x00C4` | `RIPLEY` | unresolved |
| `0x100` | `0x000A` | `HAL9000` | unresolved |
| `0x013` | `0x0A13` | `APOLLO13` | `A13` strongly resembles part of `APOLLO13` |
| `0x306` | `0x00B0` | `BORG` | possibly `B0` as hexspeak for the beginning of `BORG`; unproven |
| `0x198` | `0x0088` | `MORRIS` | `88` plausibly points to the 1988 Morris worm |
| `0x4A7` | `0x0010` | `LOG4SHELL` | possibly points to severity `10.0`; unproven |
| `0x313` | `0x00DC` | `DETROIT` likely | `DC` + APID `313` gives `DC313`, a DEF CON group associated with Detroit |

The field itself should therefore be labeled **Query ID**, not `Unknown16` or `Query Tag`. The possible semantic relationships above are a separate challenge-design hypothesis and are not required for protocol decoding.

---

## Attack Summary

```text
spacecraft_capture.pcap
    └── UDP
        └── CCSDS Space Packets
            └── Identify segmented QRY1 messages
                └── Reassemble using CCSDS sequence flags/counts
                    └── Parse 12-byte QRY1 envelope
                        ├── Query ID
                        ├── Encoded Length
                        ├── Plaintext CRC-32
                        └── Encoded Payload
                            └── XOR every byte with 0x5A
                                └── zlib / DEFLATE decompress
                                    └── Recover ASCII questions
                                        └── APID 0x341 asks for the
                                            7.5-million-year result
                                                └── Answer = "42"
                                                    └── CRC-16-CCITT-ZERO("42")
                                                        = DF40
                                                            └── NECext
                                                                Address = CAFE0000
                                                                Command = DF400000
```

---

## Flag

```text
flag(CAFE0000,DF400000}
```
