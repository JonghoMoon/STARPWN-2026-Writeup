# Strange Holos 5

| | |
|---|---|
| **Category** | Misc |
| **Points** | 442 |
| **Solves** | 193 |

## Description

A Glittercity billboard reads **DON'T PANIC** in faded letters. Projected over it in neon is a two-line cipher. A discarded "TOWEL DAY — Always know where your towel is" flyer lies on the ground.

**Attachments:** `space5-glitter.png`

![Attchments](./challenges/space5-glitter.png)

## Solution

### Steps

**1. Read the ciphertext**

The neon projection on the billboard reads:

```
IE BEDW QDT JXQDAI
VEH QBB JXU FXYIX
```

**2. Spot the contextual hints**

The background billboard says **DON'T PANIC** and the ground flyer references **TOWEL DAY** — both iconic phrases from *The Hitchhiker's Guide to the Galaxy* by Douglas Adams. The original novel famously ends with the dolphins leaving Earth with the message *"So long, and thanks for all the fish."*

**3. Identify the cipher**

The ciphertext uses Latin characters shifted by a fixed amount — a Caesar cipher. Testing shift 16 (subtract 16 from each letter mod 26):

```
IE BEDW QDT JXQDAI VEH QBB JXU FXYIX
→ SO LONG AND THANKS FOR ALL THE PHISH
```

Note: "PHISH" instead of "FISH" is an intentional twist on the original quote.

**4. Read the flag**

The decoded inscription is the flag itself.

## Flag

```
so long and thanks for all the phish
```
