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

**Attachments:** `spacecraft_capture.pcap`, `decode_qry_apid.py`

## Solution

### Steps

**1. Parse the PCAP and extract CCSDS packets**

The capture contains CCSDS (Consultative Committee for Space Data Systems) Space Packets transported over UDP. Extract the byte stream, split by APID, and identify fragmented packets using the sequence flags. Reassemble fragmented payloads into complete application-layer messages.

```bash
python3 decode_qry_apid.py <APID>
```

**2. Reassemble QRY1 / RSP1 conversations**

After reconstruction, eight complete `QRY1` request messages were recovered. Each `QRY1` was matched with a corresponding `RSP1` ground station response using correlation fields:

| APID | Ground Station Response | Correlation Field |
|------|------------------------|-------------------|
| 0x341 | RETRY | 85b6d49a |
| 0x219 | **41** | 940f1e28 |
| 0x100 | NOMINAL | ed65a4fb |
| 0x013 | NOMINAL | f558ed49 |
| 0x306 | APOLLO11 | c5988fbb |
| 0x198 | **41** | 00809840 |
| 0x4A7 | UNKNOWN | ea715537 |
| 0x313 | SKYNET | 3f584b71 |

**3. Identify the incorrect repeated response**

The challenge states *"the ground station repeatedly answers incorrectly."* Only the response `41` appears twice across all conversations — this is the intentionally incorrect answer. The natural correct answer is therefore:

```
42
```

(A classic reference to *The Hitchhiker's Guide to the Galaxy*: "the answer to life, the universe, and everything.")

**4. Determine the address**

The reconstructed application packets consistently use the address field:

```
CAFE
```

Therefore the NECext address is `CAFE0000`.

**5. Compute the NECext command**

The challenge specifies:

```
Command = CRC-16-CCITT-ZERO(ANSWER in all caps)
```

```python
import crcmod
crc_fn = crcmod.predefined.mkCrcFun('crc-ccitt-false')  # CRC-16-CCITT-ZERO
answer = "42".encode('ascii')
print(hex(crc_fn(answer)))   # → 0xdf40
```

Result: `DF40` → padded to `DF400000`

**6. Transmit via NECext IR protocol**

Send the NECext IR command to the spacecraft:

```
Address : CAFE0000
Command : DF400000
```

The spacecraft accepts the response and acknowledges through its onboard indicators.

**7. Reconstructed QRY1 Layout**

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

### Attack Summary

```
spacecraft_capture.pcap
    └── Extract CCSDS stream (UDP transport)
        └── Split by APID → reassemble fragmented payloads
            └── Match QRY1 ↔ RSP1 conversations
                └── Find repeated incorrect response: "41"
                    └── Infer correct answer: "42"
                        └── CRC-16-CCITT-ZERO("42") = DF40
                            └── NECext IR transmission
                                    Address = CAFE0000
                                    Command = DF400000
```

## Flag

```
flag(CAFE0000,DF400000}
```
