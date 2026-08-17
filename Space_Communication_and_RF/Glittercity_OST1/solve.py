#!/usr/bin/env python3

import argparse
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal


SAMPLE_RATE: int = 48_000
BAUD_RATE: int = 300
SAMPLES_PER_SYMBOL: int = SAMPLE_RATE // BAUD_RATE
SIGNAL_START_SECONDS: float = 15.0
SYMBOL_COUNT: int = 27_500
TONE_DEVIATION_HZ: float = 1_000.0
TONE_SEPARATION_HZ: float = 2.0 * TONE_DEVIATION_HZ


def decode_mp3_stereo(path: Path) -> np.ndarray:
    """Decode the input MP3 to signed 16-bit stereo PCM with ffmpeg."""
    command: list[str] = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "2",
        "-ar",
        str(SAMPLE_RATE),
        "pipe:1",
    ]
    result = subprocess.run(command, check=True, stdout=subprocess.PIPE)
    pcm: np.ndarray = np.frombuffer(result.stdout, dtype="<i2")
    if int(pcm.size) % 2 != 0:
        raise ValueError("Decoded PCM does not contain complete stereo frames")
    stereo: np.ndarray = pcm.reshape((-1, 2)).astype(np.float64)
    return stereo / float(2**15)


def parabolic_peak(magnitude: np.ndarray, index: int, bin_hz: float) -> float:
    """Refine an FFT-bin peak with log-magnitude parabolic interpolation."""
    if index <= 0 or index >= int(magnitude.size) - 1:
        return float(index) * bin_hz
    left: float = float(np.log(float(magnitude[index - 1]) + 1e-30))
    center: float = float(np.log(float(magnitude[index]) + 1e-30))
    right: float = float(np.log(float(magnitude[index + 1]) + 1e-30))
    denominator: float = left - (2.0 * center) + right
    offset: float = 0.0 if abs(denominator) < 1e-20 else 0.5 * (left - right) / denominator
    return (float(index) + offset) * bin_hz


def track_low_tone(side: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Track the lower FSK tone while both tones undergo Doppler drift."""
    fft_size: int = 32_768
    hop_size: int = 8_192
    window: np.ndarray = np.hanning(fft_size).astype(np.float64)
    bin_hz: float = float(SAMPLE_RATE) / float(fft_size)
    tone_bin_offset: int = int(round(TONE_SEPARATION_HZ / bin_hz))

    start_sample: int = int(round(SIGNAL_START_SECONDS * float(SAMPLE_RATE)))
    end_sample: int = start_sample + (SYMBOL_COUNT * SAMPLES_PER_SYMBOL)
    first_frame: int = max(0, start_sample - (fft_size // 2))
    last_frame: int = min(int(side.size) - fft_size, end_sample - (fft_size // 2))

    track_times: list[float] = []
    raw_frequencies: list[float] = []
    duration_seconds: float = float(SYMBOL_COUNT) / float(BAUD_RATE)

    for frame_start in range(first_frame, last_frame + 1, hop_size):
        center_sample: int = frame_start + (fft_size // 2)
        time_seconds: float = float(center_sample) / float(SAMPLE_RATE)
        normalized_time: float = (time_seconds - SIGNAL_START_SECONDS) / duration_seconds
        normalized_time = float(np.clip(normalized_time, 0.0, 1.0))

        # A broad linear prediction only limits the search region. The FFT pair score
        # finds the actual curved Doppler trajectory.
        predicted_low_hz: float = 12_300.0 + ((8_100.0 - 12_300.0) * normalized_time)
        spectrum: np.ndarray = np.abs(
            np.fft.rfft(side[frame_start : frame_start + fft_size] * window)
        )

        low_index: int = max(1, int(round((predicted_low_hz - 700.0) / bin_hz)))
        high_index: int = min(
            int(spectrum.size) - tone_bin_offset - 2,
            int(round((predicted_low_hz + 700.0) / bin_hz)),
        )
        candidates: np.ndarray = np.arange(low_index, high_index + 1, dtype=np.int64)
        pair_score: np.ndarray = np.sqrt(
            spectrum[candidates] * spectrum[candidates + tone_bin_offset]
        )
        best_index: int = int(candidates[int(np.argmax(pair_score))])
        low_hz: float = parabolic_peak(spectrum, best_index, bin_hz)

        track_times.append(time_seconds)
        raw_frequencies.append(low_hz)

    times: np.ndarray = np.asarray(track_times, dtype=np.float64)
    raw: np.ndarray = np.asarray(raw_frequencies, dtype=np.float64)
    if int(raw.size) < 21:
        raise ValueError("Not enough FFT frames to track the Doppler curve")

    first_smooth_length: int = min(51, int(raw.size) if int(raw.size) % 2 == 1 else int(raw.size) - 1)
    first_smooth: np.ndarray = signal.savgol_filter(raw, first_smooth_length, 3)
    cleaned: np.ndarray = raw.copy()
    outliers: np.ndarray = np.abs(raw - first_smooth) > 90.0
    cleaned[outliers] = first_smooth[outliers]

    final_smooth_length: int = min(41, int(cleaned.size) if int(cleaned.size) % 2 == 1 else int(cleaned.size) - 1)
    smooth: np.ndarray = signal.savgol_filter(cleaned, final_smooth_length, 3)
    return times, smooth.astype(np.float64)


def symbol_energy_contrast(
    side: np.ndarray,
    start_sample: int,
    symbol_index: int,
    track_times: np.ndarray,
    low_track_hz: np.ndarray,
    window: np.ndarray,
    sample_indices: np.ndarray,
) -> float:
    """Return normalized high-tone versus low-tone matched-filter contrast."""
    symbol_start: int = start_sample + (symbol_index * SAMPLES_PER_SYMBOL)
    segment: np.ndarray = side[symbol_start : symbol_start + SAMPLES_PER_SYMBOL] * window
    midpoint: float = float(symbol_start + (SAMPLES_PER_SYMBOL // 2)) / float(SAMPLE_RATE)
    low_hz: float = float(np.interp(midpoint, track_times, low_track_hz))
    center_hz: float = low_hz + TONE_DEVIATION_HZ

    low_oscillator: np.ndarray = np.exp(
        -2j * np.pi * (center_hz - TONE_DEVIATION_HZ) * sample_indices / float(SAMPLE_RATE)
    )
    high_oscillator: np.ndarray = np.exp(
        -2j * np.pi * (center_hz + TONE_DEVIATION_HZ) * sample_indices / float(SAMPLE_RATE)
    )
    low_value: complex = complex(np.dot(segment, low_oscillator))
    high_value: complex = complex(np.dot(segment, high_oscillator))
    low_energy: float = float((low_value.real**2) + (low_value.imag**2))
    high_energy: float = float((high_value.real**2) + (high_value.imag**2))
    return (high_energy - low_energy) / (high_energy + low_energy + 1e-30)


def choose_start_offset(
    side: np.ndarray,
    track_times: np.ndarray,
    low_track_hz: np.ndarray,
) -> int:
    """Tune the MP3-decoder/sample-boundary offset around the nominal 15-second start."""
    nominal_start: int = int(round(SIGNAL_START_SECONDS * float(SAMPLE_RATE)))
    window: np.ndarray = np.hanning(SAMPLES_PER_SYMBOL).astype(np.float64)
    sample_indices: np.ndarray = np.arange(SAMPLES_PER_SYMBOL, dtype=np.float64)

    best_score: float = -1.0
    best_offset: int = 0
    for offset in range(-80, 81, 4):
        scores: list[float] = []
        for symbol_index in range(0, SYMBOL_COUNT, 20):
            contrast: float = symbol_energy_contrast(
                side,
                nominal_start + offset,
                symbol_index,
                track_times,
                low_track_hz,
                window,
                sample_indices,
            )
            scores.append(abs(contrast))
        score: float = float(np.mean(np.asarray(scores, dtype=np.float64)))
        if score > best_score:
            best_score = score
            best_offset = offset

    coarse_offset: int = best_offset
    for offset in range(coarse_offset - 6, coarse_offset + 7):
        scores = []
        for symbol_index in range(0, SYMBOL_COUNT, 10):
            contrast = symbol_energy_contrast(
                side,
                nominal_start + offset,
                symbol_index,
                track_times,
                low_track_hz,
                window,
                sample_indices,
            )
            scores.append(abs(contrast))
        score = float(np.mean(np.asarray(scores, dtype=np.float64)))
        if score > best_score:
            best_score = score
            best_offset = offset

    return best_offset


def demodulate_bits(
    side: np.ndarray,
    start_sample: int,
    track_times: np.ndarray,
    low_track_hz: np.ndarray,
) -> np.ndarray:
    """Noncoherently demodulate all 300-baud BFSK symbols."""
    total_samples: int = SYMBOL_COUNT * SAMPLES_PER_SYMBOL
    signal_end: int = start_sample + total_samples
    if start_sample < 0 or signal_end > int(side.size):
        raise ValueError("The expected FSK interval is outside the decoded audio")

    symbols: np.ndarray = side[start_sample:signal_end].reshape(
        (SYMBOL_COUNT, SAMPLES_PER_SYMBOL)
    )
    window: np.ndarray = np.hanning(SAMPLES_PER_SYMBOL).astype(np.float64)
    sample_indices: np.ndarray = np.arange(SAMPLES_PER_SYMBOL, dtype=np.float64)
    midpoint_samples: np.ndarray = (
        start_sample
        + (np.arange(SYMBOL_COUNT, dtype=np.int64) * SAMPLES_PER_SYMBOL)
        + (SAMPLES_PER_SYMBOL // 2)
    )
    midpoint_times: np.ndarray = midpoint_samples.astype(np.float64) / float(SAMPLE_RATE)
    low_hz: np.ndarray = np.interp(midpoint_times, track_times, low_track_hz)
    center_hz: np.ndarray = low_hz + TONE_DEVIATION_HZ

    decisions: np.ndarray = np.empty(SYMBOL_COUNT, dtype=np.uint8)
    chunk_size: int = 1_024
    for chunk_start in range(0, SYMBOL_COUNT, chunk_size):
        chunk_end: int = min(SYMBOL_COUNT, chunk_start + chunk_size)
        chunk_symbols: np.ndarray = symbols[chunk_start:chunk_end] * window[None, :]
        chunk_center: np.ndarray = center_hz[chunk_start:chunk_end]

        low_phase: np.ndarray = (
            -2j
            * np.pi
            * (chunk_center[:, None] - TONE_DEVIATION_HZ)
            * sample_indices[None, :]
            / float(SAMPLE_RATE)
        )
        high_phase: np.ndarray = (
            -2j
            * np.pi
            * (chunk_center[:, None] + TONE_DEVIATION_HZ)
            * sample_indices[None, :]
            / float(SAMPLE_RATE)
        )
        low_values: np.ndarray = np.sum(chunk_symbols * np.exp(low_phase), axis=1)
        high_values: np.ndarray = np.sum(chunk_symbols * np.exp(high_phase), axis=1)
        low_energy: np.ndarray = np.abs(low_values) ** 2
        high_energy: np.ndarray = np.abs(high_values) ** 2
        decisions[chunk_start:chunk_end] = (high_energy > low_energy).astype(np.uint8)

    # In this recording, the low tone represents logical 1 and the high tone logical 0.
    return decisions ^ np.uint8(1)


def find_flag_positions(bits: np.ndarray) -> list[int]:
    """Find exact 0x7E HDLC flags in the LSB-first transmitted bit stream."""
    flag: np.ndarray = np.asarray([0, 1, 1, 1, 1, 1, 1, 0], dtype=np.uint8)
    positions: list[int] = []
    for index in range(0, int(bits.size) - 7):
        if bool(np.array_equal(bits[index : index + 8], flag)):
            positions.append(index)
    return positions


def remove_bit_stuffing(bits: np.ndarray) -> tuple[np.ndarray, int]:
    """Remove every zero inserted after five consecutive one bits."""
    output: list[int] = []
    ones: int = 0
    violations: int = 0
    index: int = 0
    while index < int(bits.size):
        bit: int = int(bits[index])
        output.append(bit)
        if bit == 1:
            ones += 1
            if ones == 5:
                if index + 1 < int(bits.size) and int(bits[index + 1]) == 0:
                    index += 1
                else:
                    violations += 1
                ones = 0
        else:
            ones = 0
        index += 1
    return np.asarray(output, dtype=np.uint8), violations


def crc16_x25(data: bytes) -> int:
    """Compute reflected CRC-16/X-25, as used by HDLC FCS."""
    crc: int = 0xFFFF
    for byte_value in data:
        crc ^= int(byte_value)
        for _ in range(8):
            if (crc & 1) != 0:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (crc ^ 0xFFFF) & 0xFFFF


def extract_valid_frames(bits: np.ndarray) -> list[bytes]:
    """Split on HDLC flags, destuff payload bits, and retain CRC-valid frames."""
    positions: list[int] = find_flag_positions(bits)
    valid_frames: list[bytes] = []

    for left, right in zip(positions, positions[1:]):
        payload_start: int = left + 8
        if right <= payload_start:
            continue
        stuffed: np.ndarray = bits[payload_start:right]
        unstuffed, violations = remove_bit_stuffing(stuffed)
        if violations != 0 or int(unstuffed.size) < 24 or int(unstuffed.size) % 8 != 0:
            continue

        frame: bytes = np.packbits(unstuffed, bitorder="little").tobytes()
        if len(frame) < 3:
            continue
        expected_fcs: int = int.from_bytes(frame[-2:], byteorder="little", signed=False)
        actual_fcs: int = crc16_x25(frame[:-2])
        if expected_fcs == actual_fcs:
            valid_frames.append(frame)

    return valid_frames


def main() -> int:
    parser = argparse.ArgumentParser(description="Solve the Glittercity OST1 audio CTF")
    parser.add_argument("mp3", type=Path, help="Path to Glittercity-OST1 MP3")
    args = parser.parse_args()

    stereo: np.ndarray = decode_mp3_stereo(args.mp3)
    side: np.ndarray = (stereo[:, 0] - stereo[:, 1]) * 0.5

    track_times, low_track_hz = track_low_tone(side)
    offset: int = choose_start_offset(side, track_times, low_track_hz)
    start_sample: int = int(round(SIGNAL_START_SECONDS * float(SAMPLE_RATE))) + offset
    transmitted_bits: np.ndarray = demodulate_bits(
        side, start_sample, track_times, low_track_hz
    )
    frames: list[bytes] = extract_valid_frames(transmitted_bits)

    if not frames:
        print("No CRC-valid HDLC frame was recovered", file=sys.stderr)
        return 1

    unique_payloads: list[bytes] = []
    for frame in frames:
        payload: bytes = frame[:-2]
        if payload not in unique_payloads:
            unique_payloads.append(payload)

    print(f"sample offset: {offset:+d}")
    print(f"CRC-valid frames: {len(frames)}")
    for payload in unique_payloads:
        print(payload.decode("ascii", errors="replace"), end="")
        if not payload.endswith(b"\n"):
            print()

    combined: bytes = b"\n".join(unique_payloads)
    match = re.search(rb"STARPWN\{[^}\r\n]+\}", combined)
    if match is None:
        print("No flag string was found in valid frames", file=sys.stderr)
        return 2

    print(f"FLAG: {match.group(0).decode('ascii')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

