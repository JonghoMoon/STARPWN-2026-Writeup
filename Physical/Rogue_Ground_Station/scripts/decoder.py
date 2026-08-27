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
    query_tag: int = int.from_bytes(data[4:6], byteorder="big", signed=False)
    encoded_length: int = int.from_bytes(
        data[6:8],
        byteorder="big",
        signed=False,
    )
    correlation_id: int = int.from_bytes(
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

    # Recompress to verify the observed encoder behavior.
    recompressed: bytes = zlib.compress(plaintext, level=6)

    exact_match: bool = bool(recompressed == zlib_stream)

    print(f"File           : {path}")
    print(f"Query tag      : 0x{query_tag:04X}")
    print(f"Encoded length : {encoded_length}")
    print(f"Correlation ID : 0x{correlation_id:08X}")
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
