#!/usr/bin/env python3
"""
STARPWN 2026 - Nice day for fishing solver

Dependencies:
    pip install numpy scipy rasterio

Usage:
    python3 solve_nice_day_for_fishing.py \
        aquilon_mead_sigint_node42.sigmf-data \
        aquilon_mead_sigint_node42.sigmf-meta \
        outputs_file_1.tiff \
        outputs_file_2.tiff
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from scipy import ndimage
from scipy.optimize import linear_sum_assignment


HDLC_FLAG = np.asarray([0, 1, 1, 1, 1, 1, 1, 0], dtype=np.uint8)
FLAG_REGEX = re.compile(rb"STARPWN\.[A-Za-z0-9_]+\.")


@dataclass
class AisFrame:
    time_s: float
    raw: bytes
    payload: bytes
    message_type: int
    mmsi: Optional[int]
    decoded: dict[str, object]


@dataclass
class GeoPoint:
    lat: float
    lon: float


def crc16_x25(data: bytes) -> int:
    """Calculate CRC-16/X.25."""
    crc: int = 0xFFFF

    for byte_value in data:
        crc ^= int(byte_value)

        for _ in range(8):
            if (crc & 1) != 0:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1

    return int(crc ^ 0xFFFF)


def destuff_bits(bits: np.ndarray) -> Optional[np.ndarray]:
    """Remove HDLC zero stuffing."""
    output: list[int] = []
    ones: int = 0
    index: int = 0
    size: int = int(bits.size)

    while index < size:
        bit: int = int(bits[index])
        output.append(bit)

        if bit == 1:
            ones += 1
            if ones == 5:
                index += 1
                if index >= size or int(bits[index]) != 0:
                    return None
                ones = 0
        else:
            ones = 0

        index += 1

    return np.asarray(output, dtype=np.uint8)


def bits_to_bytes_lsb(bits: np.ndarray) -> Optional[bytes]:
    """Pack HDLC bits into bytes, LSB first."""
    bit_count: int = int(bits.size)

    if (bit_count % 8) != 0:
        return None

    result = bytearray(bit_count // 8)

    for byte_index in range(bit_count // 8):
        value: int = 0

        for bit_index in range(8):
            value |= int(bits[byte_index * 8 + bit_index]) << int(bit_index)

        result[byte_index] = int(value)

    return bytes(result)


def bytes_to_msb_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder="big")


def get_uint(bits: np.ndarray, start: int, width: int) -> int:
    value: int = 0

    for bit in bits[start:start + width]:
        value = (value << 1) | int(bit)

    return int(value)


def get_sint(bits: np.ndarray, start: int, width: int) -> int:
    value: int = int(get_uint(bits, start, width))

    if (value & (1 << int(width - 1))) != 0:
        value -= 1 << int(width)

    return int(value)


def decode_ais(payload: bytes) -> dict[str, object]:
    """Decode position and SOG fields needed for the challenge."""
    bits = bytes_to_msb_bits(payload)

    if int(bits.size) < 38:
        return {}

    message_type: int = int(get_uint(bits, 0, 6))
    mmsi: int = int(get_uint(bits, 8, 30))

    result: dict[str, object] = {
        "type": int(message_type),
        "mmsi": int(mmsi),
    }

    if message_type in (1, 2, 3) and int(bits.size) >= 168:
        sog_raw: int = int(get_uint(bits, 50, 10))
        lon_raw: int = int(get_sint(bits, 61, 28))
        lat_raw: int = int(get_sint(bits, 89, 27))

        result.update({
            "sog_kn": None if sog_raw >= 1023 else float(sog_raw) / 10.0,
            "lat": float(lat_raw) / 600000.0,
            "lon": float(lon_raw) / 600000.0,
        })

    elif message_type == 18 and int(bits.size) >= 168:
        sog_raw = int(get_uint(bits, 46, 10))
        lon_raw = int(get_sint(bits, 57, 28))
        lat_raw = int(get_sint(bits, 85, 27))

        result.update({
            "sog_kn": None if sog_raw >= 1023 else float(sog_raw) / 10.0,
            "lat": float(lat_raw) / 600000.0,
            "lon": float(lon_raw) / 600000.0,
        })

    return result


def demodulate_nrzi(
    iq: np.ndarray,
    samples_per_symbol: int,
    sample_offset: int,
) -> np.ndarray:
    """FM discriminator + AIS NRZI decode."""
    phase_delta = np.angle(iq[1:] * np.conj(iq[:-1])).astype(np.float32)

    available: int = int(phase_delta.size) - int(sample_offset)
    symbol_count: int = int(available // int(samples_per_symbol))

    trimmed = phase_delta[
        int(sample_offset):
        int(sample_offset) + int(symbol_count * samples_per_symbol)
    ]

    metric = trimmed.reshape(
        int(symbol_count), int(samples_per_symbol)
    ).sum(axis=1)

    state = (metric > 0.0).astype(np.uint8)

    decoded = np.empty_like(state)
    decoded[0] = np.uint8(0)
    decoded[1:] = (state[1:] == state[:-1]).astype(np.uint8)

    return decoded


def locate_flags(bits: np.ndarray) -> np.ndarray:
    windows = np.lib.stride_tricks.sliding_window_view(bits, 8)
    matches = np.all(windows == HDLC_FLAG, axis=1)
    return np.flatnonzero(matches).astype(np.int64)


def recover_frames(
    bits: np.ndarray,
    sample_rate: float,
    samples_per_symbol: int,
    sample_offset: int,
) -> list[AisFrame]:
    """Recover CRC-valid AIS HDLC frames."""
    flags = locate_flags(bits)
    frames: list[AisFrame] = []

    for left_value, right_value in zip(flags[:-1], flags[1:]):
        left: int = int(left_value)
        right: int = int(right_value)

        if right <= left + 8:
            continue

        destuffed = destuff_bits(bits[left + 8:right])

        if destuffed is None or int(destuffed.size) < 24:
            continue

        raw = bits_to_bytes_lsb(destuffed)

        if raw is None or len(raw) < 3:
            continue

        received_crc: int = int(raw[-2]) | (int(raw[-1]) << 8)

        if int(crc16_x25(raw[:-2])) != received_crc:
            continue

        payload: bytes = bytes(raw[:-2])
        decoded = decode_ais(payload)

        if "type" not in decoded:
            continue

        center_sample: float = (
            float(sample_offset)
            + float(left * samples_per_symbol)
            + 0.5 * float(samples_per_symbol)
        )

        frames.append(AisFrame(
            time_s=float(center_sample / float(sample_rate)),
            raw=bytes(raw),
            payload=payload,
            message_type=int(decoded["type"]),
            mmsi=int(decoded["mmsi"]),
            decoded=decoded,
        ))

    return frames


def demodulate_all(
    sigmf_data: Path,
    sample_rate: float,
) -> list[AisFrame]:
    """Try all ten symbol phases and merge duplicate valid AIS frames."""
    baud: float = 9600.0
    samples_per_symbol: int = int(round(float(sample_rate) / baud))

    iq_map = np.memmap(sigmf_data, dtype="<c8", mode="r")
    iq = np.asarray(iq_map, dtype=np.complex64)

    candidates: list[AisFrame] = []

    for offset in range(samples_per_symbol):
        bits = demodulate_nrzi(
            iq=iq,
            samples_per_symbol=int(samples_per_symbol),
            sample_offset=int(offset),
        )

        recovered = recover_frames(
            bits=bits,
            sample_rate=float(sample_rate),
            samples_per_symbol=int(samples_per_symbol),
            sample_offset=int(offset),
        )

        print(f"[AIS] offset={offset}: {len(recovered)} valid frames")
        candidates.extend(recovered)

    candidates.sort(key=lambda frame: float(frame.time_s))

    merged: list[AisFrame] = []

    for candidate in candidates:
        duplicate: bool = False

        for previous in reversed(merged[-32:]):
            delta_s: float = float(candidate.time_s - previous.time_s)

            if delta_s > 0.002:
                break

            if candidate.raw == previous.raw and abs(delta_s) < 0.002:
                duplicate = True
                break

        if not duplicate:
            merged.append(candidate)

    return merged


def haversine_m(first: GeoPoint, second: GeoPoint) -> float:
    radius_m: float = 6371000.0

    lat1: float = math.radians(float(first.lat))
    lat2: float = math.radians(float(second.lat))
    dlat: float = math.radians(float(second.lat - first.lat))
    dlon: float = math.radians(float(second.lon - first.lon))

    value: float = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2.0) ** 2
    )

    return float(2.0 * radius_m * math.asin(math.sqrt(value)))


def extract_tiff_motion(
    tiff1: Path,
    tiff2: Path,
) -> tuple[list[GeoPoint], list[GeoPoint]]:
    """Extract old/new moving-object coordinates from the two GeoTIFFs."""
    with rasterio.open(tiff1) as first_ds, rasterio.open(tiff2) as second_ds:
        first = first_ds.read()
        second = second_ds.read()

        changed = np.any(first != second, axis=0)

        labels, count = ndimage.label(
            changed,
            structure=np.ones((3, 3), dtype=np.uint8),
        )

        old_points: list[GeoPoint] = []
        new_points: list[GeoPoint] = []

        for label_index in range(1, int(count) + 1):
            rows, cols = np.where(labels == int(label_index))

            if int(rows.size) == 0:
                continue

            row: float = float(np.mean(rows))
            col: float = float(np.mean(cols))

            lon, lat = rasterio.transform.xy(
                first_ds.transform,
                row,
                col,
                offset="center",
            )

            delta: float = float(np.mean(
                second[:, rows, cols].astype(np.float64)
                - first[:, rows, cols].astype(np.float64)
            ))

            point = GeoPoint(lat=float(lat), lon=float(lon))

            if delta < 0.0:
                old_points.append(point)
            else:
                new_points.append(point)

    return old_points, new_points


def build_tracks(
    frames: list[AisFrame],
) -> dict[int, list[tuple[float, GeoPoint]]]:
    tracks: dict[int, list[tuple[float, GeoPoint]]] = defaultdict(list)

    for frame in frames:
        if frame.message_type not in (1, 2, 3, 18):
            continue

        lat_value = frame.decoded.get("lat")
        lon_value = frame.decoded.get("lon")

        if lat_value is None or lon_value is None or frame.mmsi is None:
            continue

        tracks[int(frame.mmsi)].append((
            float(frame.time_s),
            GeoPoint(lat=float(lat_value), lon=float(lon_value)),
        ))

    return dict(tracks)


def interpolate(
    reports: list[tuple[float, GeoPoint]],
    target_s: float,
    max_gap_s: float = 45.0,
) -> Optional[GeoPoint]:
    ordered = sorted(reports, key=lambda item: float(item[0]))

    before = [item for item in ordered if float(item[0]) <= float(target_s)]
    after = [item for item in ordered if float(item[0]) >= float(target_s)]

    if not before or not after:
        return None

    left_t, left_p = before[-1]
    right_t, right_p = after[0]

    gap: float = float(right_t - left_t)

    if gap > float(max_gap_s):
        return None

    if abs(gap) < 1e-12:
        return GeoPoint(lat=float(left_p.lat), lon=float(left_p.lon))

    alpha: float = float((target_s - left_t) / gap)

    return GeoPoint(
        lat=float(left_p.lat + alpha * (right_p.lat - left_p.lat)),
        lon=float(left_p.lon + alpha * (right_p.lon - left_p.lon)),
    )


def best_snapshot_time(
    tracks: dict[int, list[tuple[float, GeoPoint]]],
    image_points: list[GeoPoint],
    start_s: float,
    end_s: float,
) -> float:
    """Find the RF time that best matches one TIFF snapshot."""
    best_time: Optional[float] = None
    best_cost: float = float("inf")

    for time_s in np.arange(
        float(start_s),
        float(end_s) + 0.0001,
        0.1,
        dtype=np.float64,
    ):
        predictions: list[GeoPoint] = []

        for reports in tracks.values():
            point = interpolate(reports, float(time_s))
            if point is not None:
                predictions.append(point)

        if len(predictions) < len(image_points):
            continue

        cost = np.asarray([
            [
                haversine_m(predicted, observed)
                for observed in image_points
            ]
            for predicted in predictions
        ], dtype=np.float64)

        rows, cols = linear_sum_assignment(cost)

        if len(cols) != len(image_points):
            continue

        total: float = float(cost[rows, cols].sum())

        if total < best_cost:
            best_cost = total
            best_time = float(time_s)

    if best_time is None:
        raise RuntimeError("Could not align AIS and GeoTIFF data")

    return float(best_time)


def identify_phantoms(
    frames: list[AisFrame],
    old_points: list[GeoPoint],
    new_points: list[GeoPoint],
) -> tuple[set[int], set[int], float, float]:
    """
    Identify real and phantom moving AIS tracks.

    Each GeoTIFF snapshot is matched independently against AIS positions.
    This avoids making assumptions about which old image cluster moves to
    which new image cluster.
    """
    tracks = build_tracks(frames)

    end_s: float = float(max(frame.time_s for frame in frames))

    first_time: float = best_snapshot_time(
        tracks,
        old_points,
        10.0,
        end_s - 60.0,
    )

    second_time: float = best_snapshot_time(
        tracks,
        new_points,
        first_time + 50.0,
        min(first_time + 70.0, end_s - 1.0),
    )

    candidate_mmsis: list[int] = []

    for mmsi, reports in tracks.items():
        first_point = interpolate(reports, first_time)
        second_point = interpolate(reports, second_time)

        if first_point is None or second_point is None:
            continue

        # Remove stationary physical targets such as ASDS 1 and ASDS 2.
        movement_m: float = haversine_m(first_point, second_point)

        if movement_m < 50.0:
            continue

        candidate_mmsis.append(int(mmsi))

    def match_snapshot(
        time_s: float,
        image_points: list[GeoPoint],
    ) -> set[int]:
        predictions: list[GeoPoint] = []
        mmsis: list[int] = []

        for mmsi in candidate_mmsis:
            point = interpolate(tracks[int(mmsi)], float(time_s))

            if point is None:
                continue

            mmsis.append(int(mmsi))
            predictions.append(point)

        cost = np.asarray([
            [
                haversine_m(predicted, observed)
                for observed in image_points
            ]
            for predicted in predictions
        ], dtype=np.float64)

        rows, cols = linear_sum_assignment(cost)
        matched: set[int] = set()

        for row_index, col_index in zip(rows, cols):
            error_m: float = float(
                cost[int(row_index), int(col_index)]
            )

            # Real vessel/image matches are <= about 240 m in this capture.
            # Phantom tracks are far outside this range.
            if error_m < 300.0:
                matched.add(int(mmsis[int(row_index)]))

        return matched

    first_matched = match_snapshot(first_time, old_points)
    second_matched = match_snapshot(second_time, new_points)

    # A legitimate vessel must be confirmed by both recon snapshots.
    legitimate: set[int] = first_matched & second_matched

    phantom: set[int] = {
        int(mmsi)
        for mmsi in candidate_mmsis
        if int(mmsi) not in legitimate
    }

    return legitimate, phantom, first_time, second_time

def recover_covert_stream(
    frames: list[AisFrame],
    phantom_mmsis: set[int],
) -> bytes:
    """
    Convert phantom SOG values into ASCII.

    Example:
        83.5 knots -> int(83.5) -> 83 -> 'S'
    """
    output = bytearray()

    for frame in sorted(frames, key=lambda item: float(item.time_s)):
        if frame.mmsi is None:
            continue

        if int(frame.mmsi) not in phantom_mmsis:
            continue

        if frame.message_type not in (1, 2, 3, 18):
            continue

        sog = frame.decoded.get("sog_kn")

        if sog is None:
            continue

        ascii_value: int = int(float(sog))

        if 0 <= ascii_value <= 255:
            output.append(int(ascii_value))

    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sigmf_data", type=Path)
    parser.add_argument("sigmf_meta", type=Path)
    parser.add_argument("tiff1", type=Path)
    parser.add_argument("tiff2", type=Path)
    args = parser.parse_args()

    with args.sigmf_meta.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    sample_rate: float = float(metadata["global"]["core:sample_rate"])

    frames = demodulate_all(
        sigmf_data=args.sigmf_data,
        sample_rate=sample_rate,
    )

    print(f"[+] Total CRC-valid AIS frames: {len(frames)}")

    old_points, new_points = extract_tiff_motion(
        tiff1=args.tiff1,
        tiff2=args.tiff2,
    )

    print(f"[+] TIFF moving objects: {len(old_points)}")

    legitimate, phantom, first_time, second_time = identify_phantoms(
        frames=frames,
        old_points=old_points,
        new_points=new_points,
    )

    print(
        f"[+] Best TIFF/RF alignment: "
        f"{first_time:.1f}s -> {second_time:.1f}s"
    )

    print("[+] Legitimate moving MMSIs:")
    for mmsi in sorted(legitimate):
        print(f"    {mmsi}")

    print("[+] Phantom MMSIs:")
    for mmsi in sorted(phantom):
        print(f"    {mmsi}")

    covert = recover_covert_stream(
        frames=frames,
        phantom_mmsis=phantom,
    )

    print(f"[+] Covert stream: {covert!r}")

    match = FLAG_REGEX.search(covert)

    if match is None:
        raise SystemExit("[-] Flag not found")

    flag: str = match.group(0).decode("ascii")
    print(f"[+] FLAG: {flag}")


if __name__ == "__main__":
    main()
