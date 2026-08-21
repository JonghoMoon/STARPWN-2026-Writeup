# Strange Holos 4

| | |
|---|---|
| **Category** | Misc |
| **Points** | 470 |
| **Solves** | 140 |

## Description

An underpass hologram in Glittercity displays Latin text — but the words are scrambled in a familiar yet cryptic way.

**Attachments:** `space4-glitter.png`

![Attchments](./challenges/space4-glitter.png)

## Solution

### Steps

**1. Read the ciphertext**

The hologram displays:

```
P AX ZOCYY OHVP,
P CLUT OV TSHT
```

**2. Identify the cipher**

The text uses Latin characters but is clearly encoded. Comparing the word lengths to common English phrases reveals a Vigenère-style cipher with a repeating key applied per character position globally across all words.

**3. Determine the key**

Aligning each ciphertext letter against the expected plaintext reveals the shift pattern cycling through `7, 0, 11` (repeating period-3):

| Position | Cipher | Plain | Shift |
|----------|--------|-------|-------|
| 0 | P | I | 7 |
| 1 | A | A | 0 |
| 2 | X | M | 11 |
| 3 | Z | S | 7 |
| 4 | O | O | 0 |
| 5 | C | R | 11 |
| … | … | … | … |

**4. Decode the ciphertext**

Applying the key `[7, 0, 11]` cyclically to each letter:

```
P AX ZOCYY OHVP, P CLUT OV TSHT
→ I AM SORRY DAVE, I CANT DO THAT
```

**5. Recognize the reference**

This is the iconic line spoken by HAL 9000 in *2001: A Space Odyssey*:

> *"I'm sorry, Dave. I'm afraid I can't do that."*

**6. Read the flag**

The decoded inscription is the flag itself.

## Flag

```
I AM SORRY DAVE, I CANT DO THAT
```
