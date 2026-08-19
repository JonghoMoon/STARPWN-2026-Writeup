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

## Solution

### Steps

**1. Inspect the PCAP in Wireshark**

Open `spacecraft_capture.pcap` in Wireshark and inspect the traffic.

The capture contains UDP communication between `10.42.0.10` and `10.42.0.20`. Examining the UDP packets shows that the spacecraft communication uses ports `4242` and `4243`.

At this point, Wireshark does not automatically decode the UDP payload as CCSDS, so configure the dissector manually.

1. Open **Analyze → Decode As...**
2. Set UDP port `4242` to `CCSDS`.
3. Set UDP port `4243` to `CCSDS`.
4. Click **Save** and then **OK**.

![Wireshark Decode As](/Physical/Rogue_Ground_Station/images/wireshark-decode-as.png)

After applying the CCSDS dissector, Wireshark exposes the CCSDS primary and secondary headers, including the APID, sequence number, sequence flags, and packet length.

![CCSDS packets in Wireshark](/Physical/Rogue_Ground_Station/images/wireshark-ccsds.png)

An important observation is that the CCSDS sequence numbers and capture timestamps do not provide a consistent global ordering across the entire capture. In contrast, packets belonging to the same fragmented message follow the expected sequence order. Therefore, rather than sorting all packets globally by sequence number or timestamp, the fragmented packets should be identified using the CCSDS sequence flags and reassembled according to their fragment sequence.

The CCSDS sequence flags indicate whether a packet is the first, continuation, last, or an unsegmented packet:

- `01` — First fragment
- `00` — Continuation fragment
- `10` — Last fragment
- `11` — Unsegmented packet

**2. Parse the PCAP and extract CCSDS packets**

The capture contains CCSDS (Consultative Committee for Space Data Systems) Space Packets transported over UDP. Extract the byte stream, split by APID, and identify fragmented packets using the sequence flags. Reassemble fragmented payloads into complete application-layer messages.

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

**3. Reassemble QRY1 / RSP1 conversations**

After reconstruction, eight complete `QRY1` request messages were recovered. Each `QRY1` was matched with a corresponding `RSP1` ground station response using correlation fields:

```bash
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

**The only repeated response is 41.**

**4. Identify the incorrect repeated response**

The challenge states *"the ground station repeatedly answers incorrectly."* Only the response `41` appears twice across all conversations — this is the intentionally incorrect answer. The natural correct answer is therefore:

```
42
```

(A classic reference to *The Hitchhiker's Guide to the Galaxy*: "the answer to life, the universe, and everything.")

**5. Determine the address**

The reconstructed application packets consistently use the address field:

```
CAFE
```

Therefore the NECext address is `CAFE0000`.

**6. Compute the NECext command**

The challenge specifies:

```
Command = CRC-16-CCITT-ZERO(ANSWER in all caps)

The challenge specifies `CRC-16-CCITT-ZERO`, which uses the following parameters:

width   = 16
poly    = 0x1021
init    = 0x0000
refin   = false
refout  = false
xorout  = 0x0000
```

When using crcmod.mkCrcFun(), the polynomial must include the implicit highest-order x^16 term. Therefore, 0x1021 is passed as 0x11021:

```python
import crcmod

crc_fn = crcmod.mkCrcFun(
    0x11021, # 0x1021 with the implicit x^16 term included
    initCrc=0x0000,
    rev=False,
    xorOut=0x0000,
)

answer = b"42"

print(f"{crc_fn(answer):04X}")
```

Result: `DF40` → padded to `DF400000`

Therefore, address and command are

```
Address : CAFE0000
Command : DF400000
```

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
