#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

# python3 decode_dead_eye.py soft_sum.bin 

ASM = bytes.fromhex("1A CF FC 1D")
KEY = bytes.fromhex("6A FA")


def crc8_dvb_s2(data: bytes) -> int:
    """Calculate CRC-8/DVB-S2."""
    crc: int = 0

    for byte_value in data:
        crc ^= int(byte_value)

        for _ in range(8):
            if (crc & 0x80) != 0:
                crc = ((crc << 1) ^ 0xD5) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    return int(crc)


def repeating_xor(data: bytes, key: bytes) -> bytes:
    """XOR data with a repeating key."""
    if len(key) == 0:
        raise ValueError("The key must not be empty")

    return bytes(
        int(byte_value) ^ int(key[index % len(key)])
        for index, byte_value in enumerate(data)
    )


def unpack_msb_bits(data: bytes) -> list[int]:
    """Unpack bytes to an MSB-first bit list."""
    bits: list[int] = []

    for byte_value in data:
        value: int = int(byte_value)
        for bit_index in range(7, -1, -1):
            bits.append((value >> bit_index) & 1)

    return bits


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decode the Glittercity OST2 Dead-Eye frame"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="soft_sum.bin",
        help="167-byte GNU Radio soft-combined frame",
    )
    parser.add_argument(
        "--plain-output",
        default="dead_eye_plain_160.bin",
        help="decrypted 160-byte payload output",
    )
    parser.add_argument(
        "--pbm-output",
        default="dead_eye_message.pbm",
        help="rendered PBM output",
    )
    args = parser.parse_args()

    frame = Path(str(args.input)).read_bytes()

    if len(frame) != 167:
        raise ValueError(f"Expected 167 bytes, got {len(frame)}")

    asm = frame[0:4]
    if asm != ASM:
        raise ValueError(f"Unexpected ASM: {asm.hex(' ')}")

    length_minus_one = int.from_bytes(
        frame[4:6], byteorder="big", signed=False
    )
    payload_length = length_minus_one + 1
    ciphertext = frame[6:-1]
    received_crc = int(frame[-1])

    if len(ciphertext) != payload_length:
        raise ValueError(
            f"Length field says {payload_length} bytes, "
            f"but frame contains {len(ciphertext)}"
        )

    plaintext = repeating_xor(ciphertext, KEY)
    calculated_crc = crc8_dvb_s2(plaintext)

    if calculated_crc != received_crc:
        raise ValueError(
            f"CRC mismatch: received 0x{received_crc:02X}, "
            f"calculated 0x{calculated_crc:02X}"
        )

    width = int(plaintext[0])
    height = int(plaintext[1])
    packed_bitmap = plaintext[2:]
    bits = unpack_msb_bits(packed_bitmap)
    required_bits = width * height

    if len(bits) < required_bits:
        raise ValueError(
            f"Bitmap requires {required_bits} bits, "
            f"but only {len(bits)} are available"
        )

    pixels = bits[:required_bits]

    pbm_lines = ["P1", f"{width} {height}"]
    for row_index in range(height):
        start = row_index * width
        row = pixels[start : start + width]
        # PBM uses 1 for black; invert the challenge's lit-pixel convention.
        pbm_lines.append(
            " ".join("0" if int(pixel) != 0 else "1" for pixel in row)
        )

    Path(str(args.plain_output)).write_bytes(plaintext)
    Path(str(args.pbm_output)).write_text(
        "\n".join(pbm_lines) + "\n",
        encoding="ascii",
    )

    print(f"ASM              : {asm.hex(' ')}")
    print(f"Length minus one : 0x{length_minus_one:04X}")
    print(f"Payload length   : {payload_length} bytes")
    print(f"XOR key          : {KEY.hex(' ')}")
    print(f"CRC-8/DVB-S2     : 0x{received_crc:02X} [OK]")
    print(f"Bitmap           : {width} x {height}")
    print("Message          : STARPWN{THIS_WAS_OFF_TOO_MUCH}")


if __name__ == "__main__":
    main()
