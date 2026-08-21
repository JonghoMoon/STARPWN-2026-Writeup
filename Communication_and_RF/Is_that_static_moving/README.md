# Is that static...moving?

| | |
|---|---|
| **Category** | Communication & RF |
| **Points** | 500 |
| **Solves** | 16 |

## Description

You got a weird signal in one of your first SynNodes. Apparently it was pointing at an old decomms'd satellite, this should have been long dead but it seems to be resurrected long enough for you to receive a message from it. Who knows when it'll go down again so you better rush.

**Attachments:** `nc 0.cloud.chals.io 25009` (ZMQ PUB endpoint)

## Solution

### Steps

**1. Capture the ZMQ signal**

The challenge exposes a ZMQ PUB socket streaming float32 I/Q samples at 2 Msps. Connect and dump the raw signal to disk:

```python
# zmq_sub.py
import zmq, sys

HOST = "0.cloud.chals.io"
PORT = 32927

ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.connect(f"tcp://{HOST}:{PORT}")
sock.setsockopt(zmq.SUBSCRIBE, b"")

with open("synnode_signal.bin", "wb") as f:
    while True:
        msg = sock.recv_multipart()
        for part in msg:
            f.write(part)
```

**2. Identify the signal chain**

Analyzing the captured IQ reveals a **DVB-S2** satellite broadcast signal with the following parameters:

| Parameter | Value |
|-----------|-------|
| Symbol rate | 2 Msps |
| Modulation | 8PSK |
| Code rate | 3/5 |
| Frame type | Normal |
| Pilots | Off |

**3. Decode the DVB-S2 signal**

Demodulate and decode the signal through the full DVB-S2 stack:

```
ZMQ float32 I/Q
→ 8PSK demodulation
→ LDPC / BCH decoding
→ BBFRAME → MPEG-TS extraction
→ H.264 video stream
```

Use `extract_synnode_flag_standalone.py` to automate the full pipeline from the captured binary.

```bash
python3 extract_synnode_flag_standalone.py synnode_signal.bin
```

**4. Extract the flag from motion vectors**

The decoded H.264 video stream contains moving white dots on a dark background. The flag is encoded in the **motion vectors** of the video — the movement pattern of the dots spells out the flag when analyzed frame by frame.

The extracted video frame shows the flag text rendered as a motion artifact:

```
STARPWN{
sn0wf4ll_1n_
$umm3r}
```

### Signal Chain Summary

```
ZMQ PUB (tcp://0.cloud.chals.io:32927)
  └─ float32 I/Q @ 2 Msps
      └─ DVB-S2 (8PSK 3/5, Normal frames, pilots off)
          └─ LDPC + BCH decoding
              └─ BBFRAME → MPEG-TS
                  └─ H.264 video
                      └─ Motion vector analysis → flag
```

## Flag

![Flag](/images/synnode_motion_flag_ori.png)

```
STARPWN{sn0wf4ll_1n_$umm3r}
```
