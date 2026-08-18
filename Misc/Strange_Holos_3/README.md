# Strange Holos 3

| | |
|---|---|
| **Category** | Misc |
| **Points** | 443 |
| **Solves** | 191 |

## Description

A rooftop hologram in Glittercity displays readable Latin text — but something is off. The words don't make sense as-is.

**Attachments:** `space3-glitter.png`

![Attchments](/Misc/Strange_Holos_3/challenges/space3-glitter.png)

## Solution

### Steps

**1. Read the ciphertext**

The hologram displays:

```
Obj gvrf ner pbby!
```

**2. Identify the cipher**

The text is readable Latin characters but meaningless — a classic sign of a simple substitution cipher. Trying ROT13 (rotate each letter by 13 positions) immediately produces a sensible phrase.

**3. Decode with ROT13**

```
Obj gvrf ner pbby!
→ Bow ties are cool!
```

This is a famous quote from the Eleventh Doctor in *Doctor Who* — another sci-fi franchise reference consistent with the Strange Holos series.

**4. Read the flag**

The decoded inscription is the flag itself.

## Flag

```
Bow ties are cool!
```
