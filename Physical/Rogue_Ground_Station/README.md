
# Rogue Ground Station

| Item | Value |
|------|-------|
| **Category** | Communication & RF |
| **Points** | 500 |
| **Solves** | 2 |

## Description

Prismantir managed to tap into the communication channel between one of
our satellites and its ground station.

The captured traffic indicates that the spacecraft repeatedly requests
information, but the ground station continues responding with incorrect
answers.

Your task is to analyze the captured communication, recover one valid
answer, and impersonate the ground station by transmitting a valid
NECext infrared command to the spacecraft.

Flag format:

```text
flag(AddressHex,CommandHex)
```

---

## Key Hints

The challenge description already provides several important clues.

1. **The packet capture contains a dialogue**, not independent packets.
   Therefore the first objective is to reconstruct complete request /
   response pairs.

2. **The ground station repeatedly answers incorrectly.**
   This indicates that identical wrong answers should appear multiple
   times in the reconstructed conversations.

3. **Only one correct answer is required.**
   It is unnecessary to fully reverse every application payload if one
   valid response can be inferred.

4. **The final transmission uses the NECext protocol.**
   The recovered answer must therefore be converted into an NECext
   command using the algorithm described in the challenge.

---

# Files

- `spacecraft_capture.pcap`
- `decode_qry_apid.py`

---

# Solution

## 1. Parse the PCAP

The supplied capture contains CCSDS packets transported over UDP.

The first step is to extract the CCSDS byte stream, split packets by APID, identify fragmented CCSDS packets using the sequence flags, and reconstruct the application payload.

```bash
python3 decode_qry_apid.py <APID>
```

This reconstructs complete application-layer payloads for each APID.

---

## 2. Reassemble QRY1 / RSP1 Conversations

After reconstruction, eight complete `QRY1` messages were recovered.

Each `QRY1` request could be matched with a corresponding `RSP1` response using the correlation fields.

| APID | Ground Station Response | Field (4B) |
|------|-------------------------|------------|
| 0x341 | RETRY | 85b6d49a |
| 0x219 | **41** | 940f1e28 |
| 0x100 | NOMINAL | ed65a4fb |
| 0x013 | NOMINAL | f558ed49 |
| 0x306 | APOLLO11 | c5988fbb |
| 0x198 | **41** | 00809840 |
| 0x4A7 | UNKNOWN | ea715537 |
| 0x313 | SKYNET | 3f584b71 |

Among the reconstructed conversations, only the response **41** appears twice.

---

## 3. Reconstructed QRY1 Layout

The application payload format could be partially reconstructed.

```
QRY1            4 bytes   ASCII identifier
ID              2 bytes   Correlation ID
Length          2 bytes   Payload length
Unknown32       4 bytes   Unknown field

-----------------------------------------
0x22 0xC6       Constant
Subtype         1 byte
Field A         2 bytes
Field B         2 bytes
Ancillary       4 bytes
Body            Variable
```

Although the packet structure was recovered, the semantic meaning of the body could not be fully decoded despite several days of analysis.

---

## 4. Recover the Correct Answer

The challenge description contains the critical clue:

> *"...the ground station repeatedly answers incorrectly."*

Since only **41** is repeated across the reconstructed conversations, it is identified as the intentionally incorrect response mentioned in the problem.

The challenge requires sending **one correct answer**, so the natural correction is inferred to be:

```
42
```

---

## 5. Determine the Address

The reconstructed application packets consistently use the common address:

```
CAFE
```

Therefore the NECext address is:

```
CAFE0000
```

---

## 6. Construct the NECext Command

The challenge specifies:

```
Command = CRC-16-CCITT-ZERO(ANSWER)
```

Using the inferred answer:

```
ANSWER = "42"
```

produces

```
CRC16-CCITT-ZERO("42") = DF40
```

Thus:

```
Address : CAFE0000
Command : DF400000
```

---

# Attack Summary

```text
spacecraft_capture.pcap
        │
        ├── Extract CCSDS stream
        ├── Split by APID
        ├── Reassemble fragmented payloads
        ├── Match QRY1 ↔ RSP1
        ├── Find repeated incorrect response ("41")
        ├── Infer correct answer ("42")
        ├── CRC16-CCITT-ZERO("42") → DF40
        └── Transmit NECext
                Address = CAFE0000
                Command = DF400000
```

---

# Flag

```text
flag(CAFE0000,DF400000)
```
