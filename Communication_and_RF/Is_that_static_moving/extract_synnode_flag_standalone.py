#!/usr/bin/env python3
import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np

PART_SEP = b"\n---PART---\n"

PLFRAME_SYMBOLS = 21690
PLHEADER_SYMBOLS = 90
PAYLOAD_SYMBOLS = 21600
KBCH = 38688
DFL_BITS = 38608
UPL_BITS = 1504
TS_PACKET_BYTES = 188


def strip_zmq_separators(src: Path) -> bytes:
    raw = src.read_bytes()
    parts = raw.split(PART_SEP)
    payload = b"".join(part for part in parts if len(part) > 0)
    print(f"[+] ZMQ payload bytes: {len(payload)}")
    return payload


def make_sof_symbols() -> np.ndarray:
    sof = 0x18D2E82
    bits = np.array([(sof >> (25 - i)) & 1 for i in range(26)], dtype=np.uint8)
    amp = float(1.0 / np.sqrt(2.0))
    symbols = np.empty(26, dtype=np.complex64)

    for i in range(26):
        bit = int(bits[i])
        value = float(amp * (1 - 2 * bit))
        if ((i + 1) & 1) != 0:
            symbols[i] = np.complex64(complex(value, value))
        else:
            symbols[i] = np.complex64(complex(-value, value))

    return symbols


def bytes_to_symbols(raw: bytes) -> np.ndarray:
    if (len(raw) % 8) != 0:
        raise RuntimeError("IQ byte count is not a multiple of one CF32 sample")

    floats = np.frombuffer(raw, dtype="<f4")
    i_samples = floats[0::2].astype(np.float32, copy=False)
    q_samples = floats[1::2].astype(np.float32, copy=False)
    complex_samples = i_samples.astype(np.complex64) + np.complex64(1j) * q_samples.astype(np.complex64)

    # The challenge waveform is exactly 2 complex samples per symbol.
    symbols = complex_samples[::2].astype(np.complex64, copy=False)
    print(f"[+] Complex samples: {int(complex_samples.size)}")
    print(f"[+] Symbol samples:  {int(symbols.size)}")
    return symbols


def find_frame_starts(symbols: np.ndarray, sof_symbols: np.ndarray) -> np.ndarray:
    # np.correlate performs conjugation of the second argument for complex input.
    corr = np.abs(np.correlate(symbols, sof_symbols, mode="valid"))
    peak = int(np.argmax(corr))
    residue = int(peak % PLFRAME_SYMBOLS)

    starts = np.arange(
        residue,
        int(symbols.size) - PLFRAME_SYMBOLS + 1,
        PLFRAME_SYMBOLS,
        dtype=np.int64,
    )

    if starts.size == 0:
        raise RuntimeError("No complete DVB-S2 PLFRAME was found")

    # Verify that all predicted frame locations correlate strongly with the SOF.
    sof_energy = float(np.sum(np.abs(sof_symbols)))
    scores = []
    for start in starts:
        value = abs(np.vdot(sof_symbols, symbols[int(start):int(start) + 26]))
        scores.append(float(value / sof_energy))

    print(f"[+] DVB-S2 frame residue: {residue} mod {PLFRAME_SYMBOLS}")
    print(f"[+] Complete PLFRAMEs:    {int(starts.size)}")
    print(f"[+] SOF score range:      {min(scores):.4f} .. {max(scores):.4f}")
    return starts


def make_pl_rotation_sequence(length: int) -> np.ndarray:
    # DVB-S2 physical-layer scrambling sequence n=0.
    period = (1 << 18) - 1
    x = np.zeros(period, dtype=np.uint8)
    y = np.zeros(period, dtype=np.uint8)
    x[0] = np.uint8(1)
    y[:18] = np.uint8(1)

    for i in range(period - 18):
        x[i + 18] = np.uint8(x[i + 7] ^ x[i])
        y[i + 18] = np.uint8(y[i + 10] ^ y[i + 7] ^ y[i + 5] ^ y[i])

    idx = np.arange(length, dtype=np.int64)
    z0 = x[idx] ^ y[idx]
    shifted = (idx + 131072) % period
    z1 = x[shifted] ^ y[shifted]
    rotation = (np.uint8(2) * z1 + z0).astype(np.uint8)
    return rotation


def make_bb_prbs(length: int) -> np.ndarray:
    # DVB-S2 BB scrambler: 1 + X^14 + X^15, initialized to 100101010000000.
    reg = np.array(
        [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0],
        dtype=np.uint8,
    )
    out = np.empty(length, dtype=np.uint8)

    for i in range(length):
        feedback = np.uint8(reg[13] ^ reg[14])
        out[i] = feedback
        reg[1:] = reg[:-1]
        reg[0] = feedback

    return out


def crc8_dvb_s2(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= int(byte)
        for _ in range(8):
            if (crc & 0x80) != 0:
                crc = ((crc << 1) ^ 0xD5) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return int(crc)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    if (int(bits.size) % 8) != 0:
        raise RuntimeError("Bit count is not byte aligned")
    return np.packbits(bits.astype(np.uint8, copy=False), bitorder="big").tobytes()


def demap_frame(
    symbols: np.ndarray,
    start: int,
    sof_symbols: np.ndarray,
    pl_rotation: np.ndarray,
    bb_prbs: np.ndarray,
) -> tuple[bytes, bytes]:
    frame_start = int(start)

    # Resolve the common carrier phase from the known SOF.
    rx_sof = symbols[frame_start:frame_start + 26]
    phase = float(np.angle(np.vdot(sof_symbols, rx_sof)))
    carrier_fix = np.complex64(np.exp(-1j * phase))

    payload = symbols[
        frame_start + PLHEADER_SYMBOLS:frame_start + PLFRAME_SYMBOLS
    ].astype(np.complex64, copy=True)
    payload *= carrier_fix

    # Remove DVB-S2 physical-layer QPSK rotations.
    rotations = np.exp(-1j * pl_rotation.astype(np.float64) * (np.pi / 2.0)).astype(np.complex64)
    payload *= rotations

    angles = np.mod(np.angle(payload).astype(np.float64), 2.0 * np.pi)
    phase_index = np.rint(angles / (np.pi / 4.0)).astype(np.int16) & 7

    # DVB-S2 8PSK Gray mapping, expressed for the phase convention in this capture.
    # phase: 0,45,90,...315 deg -> 100,000,001,011,010,110,111,101
    phase_to_bits = np.array(
        [
            [1, 0, 0],
            [0, 0, 0],
            [0, 0, 1],
            [0, 1, 1],
            [0, 1, 0],
            [1, 1, 0],
            [1, 1, 1],
            [1, 0, 1],
        ],
        dtype=np.uint8,
    )
    interleaved = phase_to_bits[phase_index]

    # For this 8PSK 3/5 waveform, the three interleaver columns are recovered
    # directly from the three bits of each mapped symbol.
    fecframe = np.concatenate(
        [interleaved[:, 0], interleaved[:, 1], interleaved[:, 2]]
    ).astype(np.uint8, copy=False)

    # The LDPC and BCH encoders are systematic. This challenge capture is clean,
    # so the BBFRAME can be recovered directly from the systematic portion.
    bb_scrambled = fecframe[:KBCH]
    bbframe = bb_scrambled ^ bb_prbs

    header = bits_to_bytes(bbframe[:80])
    data_field = bits_to_bytes(bbframe[80:80 + DFL_BITS])
    return header, data_field


def recover_transport_stream(symbols: np.ndarray, ts_file: Path) -> None:
    sof_symbols = make_sof_symbols()
    starts = find_frame_starts(symbols, sof_symbols)
    pl_rotation = make_pl_rotation_sequence(PAYLOAD_SYMBOLS)
    bb_prbs = make_bb_prbs(KBCH)

    fields: list[bytes] = []
    first_syncd_bytes: int | None = None
    valid_frames = 0

    for frame_index, start in enumerate(starts):
        header, data_field = demap_frame(
            symbols,
            int(start),
            sof_symbols,
            pl_rotation,
            bb_prbs,
        )

        if len(header) != 10:
            raise RuntimeError(f"Frame {frame_index}: invalid BBHEADER size")
        if crc8_dvb_s2(header[:9]) != int(header[9]):
            raise RuntimeError(
                f"Frame {frame_index}: BBHEADER CRC mismatch ({header.hex()})"
            )

        matype1 = int(header[0])
        upl = int.from_bytes(header[2:4], "big")
        dfl = int.from_bytes(header[4:6], "big")
        sync = int(header[6])
        syncd_bits = int.from_bytes(header[7:9], "big")

        if (matype1 & 0xC0) != 0xC0:
            raise RuntimeError(f"Frame {frame_index}: input is not a Transport Stream")
        if upl != UPL_BITS:
            raise RuntimeError(f"Frame {frame_index}: unexpected UPL={upl}")
        if dfl != DFL_BITS:
            raise RuntimeError(f"Frame {frame_index}: unexpected DFL={dfl}")
        if sync != 0x47:
            raise RuntimeError(f"Frame {frame_index}: unexpected SYNC=0x{sync:02X}")
        if (syncd_bits % 8) != 0:
            raise RuntimeError(f"Frame {frame_index}: SYNCD is not byte aligned")

        if first_syncd_bytes is None:
            first_syncd_bytes = int(syncd_bits // 8)

        fields.append(data_field)
        valid_frames += 1

    if first_syncd_bytes is None:
        raise RuntimeError("No valid BBFRAME was recovered")

    print(f"[+] Valid BBFRAMEs:       {valid_frames}")
    print(f"[+] First SYNCD:          {first_syncd_bytes} bytes")

    # Concatenating DATAFIELDs recreates the continuous Mode Adaptation stream.
    # At each UPL boundary, the first byte is the DVB-S2 CRC replacement for the
    # original TS sync byte. Restore it to 0x47.
    mode_stream = b"".join(fields)
    complete_packets = int((len(mode_stream) - first_syncd_bytes) // TS_PACKET_BYTES)
    output = bytearray(complete_packets * TS_PACKET_BYTES)

    for i in range(complete_packets):
        begin = int(first_syncd_bytes + i * TS_PACKET_BYTES)
        end = int(begin + TS_PACKET_BYTES)
        packet = bytearray(mode_stream[begin:end])
        packet[0] = 0x47
        out_begin = int(i * TS_PACKET_BYTES)
        output[out_begin:out_begin + TS_PACKET_BYTES] = packet

    ts_file.write_bytes(bytes(output))
    digest = hashlib.sha256(bytes(output)).hexdigest()
    print(f"[+] MPEG-TS packets:      {complete_packets}")
    print(f"[+] Recovered MPEG-TS:    {ts_file}")
    print(f"[+] MPEG-TS SHA-256:      {digest}")


def extract_video_frames(ts_file: Path, frame_dir: Path) -> list[Path]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg was not found in PATH")

    frame_dir.mkdir(parents=True, exist_ok=True)
    for old in frame_dir.glob("*.png"):
        old.unlink()

    output_pattern = frame_dir / "%04d.png"
    cmd = [
        ffmpeg,
        "-loglevel",
        "error",
        "-i",
        str(ts_file),
        "-vsync",
        "0",
        str(output_pattern),
    ]
    subprocess.run(cmd, check=True)

    frames = sorted(frame_dir.glob("*.png"))
    if len(frames) < 2:
        raise RuntimeError("Too few video frames were decoded")

    print(f"[+] Decoded video frames: {len(frames)}")
    return frames


def load_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Failed to read frame: {path}")
    return image.astype(np.uint8, copy=False)


def shift_match_count(a: np.ndarray, b: np.ndarray, dx: int, dy: int) -> int:
    """Count bright points in frame A that reappear at displacement (dx, dy) in B."""
    height = int(a.shape[0])
    width = int(a.shape[1])
    y0 = int(max(0, -int(dy)))
    y1 = int(min(height, height - int(dy)))
    x0 = int(max(0, -int(dx)))
    x1 = int(min(width, width - int(dx)))

    if y1 <= y0 or x1 <= x0:
        return int(0)

    overlap = (
        a[y0:y1, x0:x1]
        & b[y0 + int(dy) : y1 + int(dy), x0 + int(dx) : x1 + int(dx)]
    )
    return int(np.count_nonzero(overlap))


def find_motion_vectors(
    frames: list[np.ndarray],
    radius: int = 3,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Find the dominant snow motion and the strongest counter-moving population."""
    binary = [(frame > np.uint8(100)) for frame in frames]
    scores: dict[tuple[int, int], int] = {}

    for dy in range(-int(radius), int(radius) + 1):
        for dx in range(-int(radius), int(radius) + 1):
            if int(dx) == 0 and int(dy) == 0:
                continue

            total = int(0)
            for first, second in zip(binary, binary[1:]):
                total += int(shift_match_count(first, second, int(dx), int(dy)))
            scores[(int(dx), int(dy))] = int(total)

    if not scores:
        raise RuntimeError("No motion candidates were measured")

    dominant = max(scores, key=scores.get)
    dom_dx = int(dominant[0])
    dom_dy = int(dominant[1])

    opposite_scores = {
        vector: int(score)
        for vector, score in scores.items()
        if int(vector[0] * dom_dx + vector[1] * dom_dy) < 0
    }
    if not opposite_scores:
        raise RuntimeError("No counter-moving point population was found")

    hidden = max(opposite_scores, key=opposite_scores.get)
    print(
        f"[+] Dominant motion:      dx={int(dominant[0]):+d}, dy={int(dominant[1]):+d} "
        f"(score {int(scores[dominant])})"
    )
    print(
        f"[+] Hidden motion:        dx={int(hidden[0]):+d}, dy={int(hidden[1]):+d} "
        f"(score {int(scores[hidden])})"
    )
    return dominant, hidden


def isolate_opposite_motion(frame_paths: list[Path], out_file: Path) -> None:
    """Extract only dots that persist at the counter-motion displacement."""
    frames = [load_gray(path) for path in frame_paths]
    _, hidden = find_motion_vectors(frames)

    dx = int(hidden[0])
    dy = int(hidden[1])
    height = int(frames[0].shape[0])
    width = int(frames[0].shape[1])
    accumulator = np.zeros((height, width), dtype=np.uint16)

    for first_gray, second_gray in zip(frames, frames[1:]):
        first = first_gray > np.uint8(100)
        second = second_gray > np.uint8(100)

        y0 = int(max(0, -dy))
        y1 = int(min(height, height - dy))
        x0 = int(max(0, -dx))
        x1 = int(min(width, width - dx))

        matches = (
            first[y0:y1, x0:x1]
            & second[y0 + dy : y1 + dy, x0 + dx : x1 + dx]
        )
        accumulator[y0:y1, x0:x1] += matches.astype(np.uint16, copy=False)

    # Keep the exact matched dot locations. Do not blur or dilate here; those
    # operations make '$', '5', 'S', '1', and 'l' unnecessarily ambiguous.
    image = (accumulator > np.uint16(0)).astype(np.uint8) * np.uint8(255)

    points = cv2.findNonZero(image)
    if points is None:
        raise RuntimeError("Counter-motion extraction produced an empty image")

    x, y, box_width, box_height = cv2.boundingRect(points)
    margin = int(20)
    x0 = int(max(0, int(x) - margin))
    y0 = int(max(0, int(y) - margin))
    x1 = int(min(width, int(x) + int(box_width) + margin))
    y1 = int(min(height, int(y) + int(box_height) + margin))
    cropped = image[y0:y1, x0:x1]

    if not bool(cv2.imwrite(str(out_file), cropped)):
        raise RuntimeError(f"Failed to write {out_file}")

    # Also write a nearest-neighbor 2x preview without changing the dot shapes.
    preview_file = out_file.with_name(f"{out_file.stem}_2x{out_file.suffix}")
    preview = cv2.resize(
        cropped,
        None,
        fx=2.0,
        fy=2.0,
        interpolation=cv2.INTER_NEAREST,
    )
    if not bool(cv2.imwrite(str(preview_file), preview)):
        raise RuntimeError(f"Failed to write {preview_file}")

    print(f"[+] Motion-separated image: {out_file}")
    print(f"[+] 2x preview:             {preview_file}")
    print("[+] The revealed text is: STARPWN{sn0wf4ll_1n_$umm3r}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone extractor for STARPWN Is that static...moving?"
    )
    parser.add_argument("input", type=Path, help="synnode_signal.bin")
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("synnode_work"),
        help="Working directory",
    )
    args = parser.parse_args()

    workdir = args.workdir
    workdir.mkdir(parents=True, exist_ok=True)

    raw_iq = strip_zmq_separators(args.input)
    symbols = bytes_to_symbols(raw_iq)

    ts_file = workdir / "synnode_recovered.ts"
    recover_transport_stream(symbols, ts_file)

    frame_dir = workdir / "frames"
    frame_paths = extract_video_frames(ts_file, frame_dir)

    out_file = workdir / "synnode_motion_flag.png"
    isolate_opposite_motion(frame_paths, out_file)


if __name__ == "__main__":
    main()
