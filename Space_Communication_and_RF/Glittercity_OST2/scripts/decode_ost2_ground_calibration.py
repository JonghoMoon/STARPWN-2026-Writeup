#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
from scipy import signal
from scipy.io import wavfile


OUTPUT_SAMPLE_RATE: Final[int] = 48_000
DEFAULT_START_SECONDS: Final[float] = 14.0
DEFAULT_END_SECONDS: Final[float] = 30.0
DEFAULT_BAUD_RATE: Final[float] = 300.0
DEFAULT_TONE_SEPARATION_HZ: Final[float] = 2_000.0
DEFAULT_LOW_SEARCH_MIN_HZ: Final[float] = 9_800.0
DEFAULT_LOW_SEARCH_MAX_HZ: Final[float] = 10_600.0
HDLC_FLAG_BITS: Final[np.ndarray] = np.asarray(
    [0, 1, 1, 1, 1, 1, 1, 0],
    dtype=np.uint8,
)


@dataclass(frozen=True)
class HdlcFrame:
    start_bit: int
    end_bit: int
    stuffed_bit_count: int
    unstuffed_bit_count: int
    removed_stuffed_zeros: int
    raw_bytes: bytes
    payload: bytes
    received_fcs: int
    calculated_fcs: int


@dataclass(frozen=True)
class DemodulationResult:
    low_tone_hz: float
    high_tone_hz: float
    samples_per_symbol: int
    symbol_phase: int
    low_tone_is_one: bool
    bits: np.ndarray
    confidence: float
    flag_count: int
    frames: tuple[HdlcFrame, ...]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract and decode the Glittercity OST2 ground-calibration "
            "300-baud 2-FSK/HDLC transmission."
        )
    )
    parser.add_argument(
        "input_mp3",
        type=Path,
        help="Path to Glittercity-OST2 MP3",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("ost2_ground_calibration"),
        help="Output directory (default: ost2_ground_calibration)",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=DEFAULT_START_SECONDS,
        help="Extraction start in seconds (default: 14.0)",
    )
    parser.add_argument(
        "--end",
        type=float,
        default=DEFAULT_END_SECONDS,
        help="Extraction end in seconds (default: 30.0)",
    )
    parser.add_argument(
        "--baud",
        type=float,
        default=DEFAULT_BAUD_RATE,
        help="FSK baud rate (default: 300)",
    )
    parser.add_argument(
        "--tone-separation",
        type=float,
        default=DEFAULT_TONE_SEPARATION_HZ,
        help="Tone separation in Hz (default: 2000)",
    )
    parser.add_argument(
        "--low-search-min",
        type=float,
        default=DEFAULT_LOW_SEARCH_MIN_HZ,
        help="Minimum lower-tone search frequency in Hz (default: 9800)",
    )
    parser.add_argument(
        "--low-search-max",
        type=float,
        default=DEFAULT_LOW_SEARCH_MAX_HZ,
        help="Maximum lower-tone search frequency in Hz (default: 10600)",
    )
    return parser.parse_args()


def run_ffmpeg(command: list[str]) -> None:
    """Run ffmpeg and convert a non-zero exit status into a readable error."""
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffmpeg failed with exit code {int(exc.returncode)}"
        ) from exc


def extract_calibration_wavs(
    input_path: Path,
    output_dir: Path,
    start_seconds: float,
    end_seconds: float,
) -> tuple[Path, Path]:
    """Extract the stereo interval and its left-minus-right side channel."""
    output_dir.mkdir(parents=True, exist_ok=True)

    stereo_path: Path = output_dir / "ground_calibration_stereo.wav"
    side_path: Path = output_dir / "ground_calibration_side.wav"
    trim_filter: str = (
        f"atrim=start={float(start_seconds):.7f}:end={float(end_seconds):.7f},"
        "asetpts=PTS-STARTPTS"
    )

    stereo_command: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-af",
        trim_filter,
        "-ar",
        str(int(OUTPUT_SAMPLE_RATE)),
        "-ac",
        "2",
        "-c:a",
        "pcm_f32le",
        str(stereo_path),
    ]
    run_ffmpeg(stereo_command)

    side_filter: str = f"{trim_filter},pan=mono|c0=0.5*c0-0.5*c1"
    side_command: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-af",
        side_filter,
        "-ar",
        str(int(OUTPUT_SAMPLE_RATE)),
        "-ac",
        "1",
        "-c:a",
        "pcm_f32le",
        str(side_path),
    ]
    run_ffmpeg(side_command)

    return stereo_path, side_path


def normalize_pcm(samples: np.ndarray) -> np.ndarray:
    """Convert a WAV array to normalized float64 samples."""
    if np.issubdtype(samples.dtype, np.floating):
        return samples.astype(np.float64, copy=False)

    if np.issubdtype(samples.dtype, np.signedinteger):
        integer_info: np.iinfo = np.iinfo(samples.dtype)
        scale: float = float(
            max(abs(int(integer_info.min)), abs(int(integer_info.max)))
        )
        return samples.astype(np.float64) / scale

    if np.issubdtype(samples.dtype, np.unsignedinteger):
        integer_info = np.iinfo(samples.dtype)
        midpoint: float = float(int(integer_info.max) + 1) / 2.0
        return (samples.astype(np.float64) - midpoint) / midpoint

    raise TypeError(f"Unsupported WAV sample type: {samples.dtype}")


def load_mono_wav(path: Path) -> tuple[int, np.ndarray]:
    """Read a mono WAV and return its sample rate and zero-mean samples."""
    sample_rate_raw: int
    samples_raw: np.ndarray
    sample_rate_raw, samples_raw = wavfile.read(str(path))

    sample_rate: int = int(sample_rate_raw)
    samples: np.ndarray = normalize_pcm(np.asarray(samples_raw))

    if samples.ndim == 2:
        if int(samples.shape[1]) != 1:
            raise ValueError(f"Expected mono WAV, got shape {samples.shape}")
        samples = samples[:, 0]
    elif samples.ndim != 1:
        raise ValueError(f"Unsupported WAV shape: {samples.shape}")

    samples = samples.astype(np.float64, copy=False)
    samples -= float(np.mean(samples))
    return sample_rate, samples


def estimate_low_tone(
    samples: np.ndarray,
    sample_rate: int,
    tone_separation_hz: float,
    search_min_hz: float,
    search_max_hz: float,
) -> float:
    """Find the lower FSK tone by scoring spectral bins separated by 2 kHz."""
    if float(search_max_hz) <= float(search_min_hz):
        raise ValueError("The lower-tone search range is invalid")

    nperseg: int = min(16_384, int(samples.size))
    if nperseg < 1_024:
        raise ValueError("The extracted WAV is too short for tone estimation")

    noverlap: int = nperseg // 2
    nfft: int = max(131_072, nperseg)
    frequencies: np.ndarray
    power: np.ndarray
    frequencies, power = signal.welch(
        samples,
        fs=float(sample_rate),
        window="hann",
        nperseg=int(nperseg),
        noverlap=int(noverlap),
        nfft=int(nfft),
        scaling="spectrum",
    )

    bin_hz: float = float(frequencies[1] - frequencies[0])
    separation_bins: int = int(round(float(tone_separation_hz) / bin_hz))
    first_index: int = int(np.searchsorted(frequencies, float(search_min_hz)))
    last_index: int = int(np.searchsorted(frequencies, float(search_max_hz)))
    last_index = min(last_index, int(power.size) - separation_bins)

    if last_index <= first_index:
        raise ValueError("The tone search range contains no usable FFT bins")

    pair_score: np.ndarray = np.sqrt(
        power[first_index:last_index]
        * power[
            first_index + separation_bins : last_index + separation_bins
        ]
    )
    best_relative_index: int = int(np.argmax(pair_score))
    best_index: int = first_index + best_relative_index
    return float(frequencies[best_index])


def calculate_sliding_contrast(
    samples: np.ndarray,
    sample_rate: int,
    samples_per_symbol: int,
    low_tone_hz: float,
    high_tone_hz: float,
) -> np.ndarray:
    """Calculate high-tone versus low-tone energy for every window start."""
    if int(samples.size) < int(samples_per_symbol):
        raise ValueError("The WAV contains fewer than one FSK symbol")

    sample_indices: np.ndarray = np.arange(
        int(samples.size),
        dtype=np.float64,
    )
    symbol_window: np.ndarray = np.hanning(int(samples_per_symbol)).astype(
        np.float64
    )

    low_mixed: np.ndarray = samples * np.exp(
        -2j
        * np.pi
        * float(low_tone_hz)
        * sample_indices
        / float(sample_rate)
    )
    high_mixed: np.ndarray = samples * np.exp(
        -2j
        * np.pi
        * float(high_tone_hz)
        * sample_indices
        / float(sample_rate)
    )

    low_values: np.ndarray = signal.fftconvolve(
        low_mixed,
        symbol_window[::-1],
        mode="valid",
    )
    high_values: np.ndarray = signal.fftconvolve(
        high_mixed,
        symbol_window[::-1],
        mode="valid",
    )

    low_energy: np.ndarray = np.abs(low_values) ** 2
    high_energy: np.ndarray = np.abs(high_values) ** 2
    return (
        (high_energy - low_energy)
        / (high_energy + low_energy + 1e-30)
    ).astype(np.float64)


def find_flag_positions(bits: np.ndarray) -> list[int]:
    """Find exact 0x7E flags in an LSB-first HDLC bit stream."""
    if int(bits.size) < int(HDLC_FLAG_BITS.size):
        return []

    windows: np.ndarray = np.lib.stride_tricks.sliding_window_view(
        bits,
        int(HDLC_FLAG_BITS.size),
    )
    matches: np.ndarray = np.all(windows == HDLC_FLAG_BITS, axis=1)
    return [int(index) for index in np.flatnonzero(matches)]


def remove_bit_stuffing(bits: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Remove each zero inserted after five consecutive one bits."""
    output: list[int] = []
    consecutive_ones: int = 0
    removed_zeros: int = 0
    violations: int = 0
    index: int = 0

    while index < int(bits.size):
        bit_value: int = int(bits[index])
        output.append(bit_value)

        if bit_value == 1:
            consecutive_ones += 1
            if consecutive_ones == 5:
                if index + 1 < int(bits.size) and int(bits[index + 1]) == 0:
                    index += 1
                    removed_zeros += 1
                else:
                    violations += 1
                consecutive_ones = 0
        else:
            consecutive_ones = 0

        index += 1

    return (
        np.asarray(output, dtype=np.uint8),
        int(removed_zeros),
        int(violations),
    )


def crc16_x25(data: bytes) -> int:
    """Compute the reflected CRC-16/X-25 value used by HDLC FCS."""
    crc_value: int = 0xFFFF

    for byte_value in data:
        crc_value ^= int(byte_value)
        for _ in range(8):
            if (crc_value & 1) != 0:
                crc_value = (crc_value >> 1) ^ 0x8408
            else:
                crc_value >>= 1

    return int((crc_value ^ 0xFFFF) & 0xFFFF)


def extract_crc_valid_frames(
    bits: np.ndarray,
) -> tuple[list[HdlcFrame], int]:
    """Split on flags, remove bit stuffing, and retain CRC-valid frames."""
    flag_positions: list[int] = find_flag_positions(bits)
    valid_frames: list[HdlcFrame] = []

    for left_flag, right_flag in zip(flag_positions, flag_positions[1:]):
        frame_start: int = int(left_flag) + 8
        frame_end: int = int(right_flag)
        if frame_end <= frame_start:
            continue

        stuffed_bits: np.ndarray = bits[frame_start:frame_end]
        unstuffed_bits: np.ndarray
        removed_zeros: int
        violations: int
        unstuffed_bits, removed_zeros, violations = remove_bit_stuffing(
            stuffed_bits
        )

        if violations != 0:
            continue
        if int(unstuffed_bits.size) < 24:
            continue
        if int(unstuffed_bits.size) % 8 != 0:
            continue

        raw_bytes: bytes = np.packbits(
            unstuffed_bits,
            bitorder="little",
        ).tobytes()
        if len(raw_bytes) < 3:
            continue

        received_fcs: int = int.from_bytes(
            raw_bytes[-2:],
            byteorder="little",
            signed=False,
        )
        calculated_fcs: int = crc16_x25(raw_bytes[:-2])
        if received_fcs != calculated_fcs:
            continue

        valid_frames.append(
            HdlcFrame(
                start_bit=int(left_flag),
                end_bit=int(right_flag),
                stuffed_bit_count=int(stuffed_bits.size),
                unstuffed_bit_count=int(unstuffed_bits.size),
                removed_stuffed_zeros=int(removed_zeros),
                raw_bytes=raw_bytes,
                payload=raw_bytes[:-2],
                received_fcs=int(received_fcs),
                calculated_fcs=int(calculated_fcs),
            )
        )

    return valid_frames, len(flag_positions)


def choose_symbol_phase(
    contrast: np.ndarray,
    samples_per_symbol: int,
    low_tone_hz: float,
    high_tone_hz: float,
) -> DemodulationResult:
    """Scan all symbol phases and both tone polarities for valid HDLC frames."""
    best_result: DemodulationResult | None = None
    best_score: tuple[int, int, float] | None = None

    for symbol_phase in range(int(samples_per_symbol)):
        sampled_contrast: np.ndarray = contrast[
            int(symbol_phase) :: int(samples_per_symbol)
        ]
        high_tone_bits: np.ndarray = (sampled_contrast > 0.0).astype(np.uint8)
        confidence: float = float(np.mean(np.abs(sampled_contrast)))

        for low_tone_is_one in (False, True):
            if low_tone_is_one:
                logical_bits: np.ndarray = high_tone_bits ^ np.uint8(1)
            else:
                logical_bits = high_tone_bits.copy()

            frames: list[HdlcFrame]
            flag_count: int
            frames, flag_count = extract_crc_valid_frames(logical_bits)
            score: tuple[int, int, float] = (
                len(frames),
                int(flag_count),
                float(confidence),
            )

            if best_score is None or score > best_score:
                best_score = score
                best_result = DemodulationResult(
                    low_tone_hz=float(low_tone_hz),
                    high_tone_hz=float(high_tone_hz),
                    samples_per_symbol=int(samples_per_symbol),
                    symbol_phase=int(symbol_phase),
                    low_tone_is_one=bool(low_tone_is_one),
                    bits=logical_bits.copy(),
                    confidence=float(confidence),
                    flag_count=int(flag_count),
                    frames=tuple(frames),
                )

    if best_result is None or len(best_result.frames) == 0:
        raise ValueError("No CRC-valid HDLC frame was recovered")

    return best_result


def unique_payloads(frames: tuple[HdlcFrame, ...]) -> list[bytes]:
    """Return payloads in first-seen order without duplicates."""
    unique: list[bytes] = []
    for frame in frames:
        if frame.payload not in unique:
            unique.append(frame.payload)
    return unique


def save_decoded_outputs(
    output_dir: Path,
    result: DemodulationResult,
    payloads: list[bytes],
) -> None:
    """Save the selected bit stream, first valid frame, and decoded text."""
    bit_text: str = "".join(str(int(bit)) for bit in result.bits)
    (output_dir / "ground_calibration.bits.txt").write_text(
        bit_text + "\n",
        encoding="ascii",
    )

    if len(result.frames) > 0:
        (output_dir / "ground_calibration.frame.bin").write_bytes(
            result.frames[0].raw_bytes
        )

    payload_blob: bytes = b"\n".join(payloads)
    (output_dir / "ground_calibration.payload.bin").write_bytes(payload_blob)
    (output_dir / "ground_calibration.payload.txt").write_text(
        payload_blob.decode("ascii", errors="replace"),
        encoding="utf-8",
    )


def main() -> int:
    args: argparse.Namespace = parse_arguments()

    input_path: Path = Path(args.input_mp3).expanduser().resolve()
    output_dir: Path = Path(args.output_dir).expanduser().resolve()
    start_seconds: float = float(args.start)
    end_seconds: float = float(args.end)
    baud_rate: float = float(args.baud)
    tone_separation_hz: float = float(args.tone_separation)
    low_search_min_hz: float = float(args.low_search_min)
    low_search_max_hz: float = float(args.low_search_max)

    if not input_path.is_file():
        print(f"[-] Input file does not exist: {input_path}", file=sys.stderr)
        return 1
    if shutil.which("ffmpeg") is None:
        print("[-] ffmpeg was not found in PATH", file=sys.stderr)
        return 1
    if start_seconds < 0.0 or end_seconds <= start_seconds:
        print("[-] Invalid extraction interval", file=sys.stderr)
        return 1
    if baud_rate <= 0.0 or tone_separation_hz <= 0.0:
        print("[-] Baud rate and tone separation must be positive", file=sys.stderr)
        return 1

    try:
        stereo_path: Path
        side_path: Path
        stereo_path, side_path = extract_calibration_wavs(
            input_path=input_path,
            output_dir=output_dir,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
        )

        sample_rate: int
        side_samples: np.ndarray
        sample_rate, side_samples = load_mono_wav(side_path)

        exact_samples_per_symbol: float = float(sample_rate) / baud_rate
        samples_per_symbol: int = int(round(exact_samples_per_symbol))
        if abs(exact_samples_per_symbol - float(samples_per_symbol)) > 1e-9:
            raise ValueError(
                f"Sample rate {int(sample_rate)} is not an integer multiple "
                f"of baud rate {float(baud_rate):.6f}"
            )

        low_tone_hz: float = estimate_low_tone(
            samples=side_samples,
            sample_rate=sample_rate,
            tone_separation_hz=tone_separation_hz,
            search_min_hz=low_search_min_hz,
            search_max_hz=low_search_max_hz,
        )
        high_tone_hz: float = low_tone_hz + tone_separation_hz

        contrast: np.ndarray = calculate_sliding_contrast(
            samples=side_samples,
            sample_rate=sample_rate,
            samples_per_symbol=samples_per_symbol,
            low_tone_hz=low_tone_hz,
            high_tone_hz=high_tone_hz,
        )
        result: DemodulationResult = choose_symbol_phase(
            contrast=contrast,
            samples_per_symbol=samples_per_symbol,
            low_tone_hz=low_tone_hz,
            high_tone_hz=high_tone_hz,
        )
        payloads: list[bytes] = unique_payloads(result.frames)
        save_decoded_outputs(output_dir, result, payloads)

    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        print(f"[-] {exc}", file=sys.stderr)
        return 1

    print(f"[*] Input              : {input_path}")
    print(
        f"[*] Extracted interval : {float(start_seconds):.4f} - "
        f"{float(end_seconds):.4f} s"
    )
    print(f"[*] Stereo WAV         : {stereo_path}")
    print(f"[*] Side-channel WAV   : {side_path}")
    print(f"[*] Sample rate        : {int(sample_rate)} Hz")
    print(f"[*] Baud rate          : {float(baud_rate):.1f}")
    print(f"[*] Samples/symbol     : {int(samples_per_symbol)}")
    print(
        f"[*] Estimated tones    : {float(result.low_tone_hz):.2f} / "
        f"{float(result.high_tone_hz):.2f} Hz"
    )
    print(f"[*] Symbol phase       : {int(result.symbol_phase)} samples")
    print(
        "[*] Tone mapping       : "
        + ("low=1, high=0" if result.low_tone_is_one else "low=0, high=1")
    )
    print(f"[*] HDLC flags found   : {int(result.flag_count)}")
    print(f"[+] CRC-valid frames   : {len(result.frames)}")

    for frame_index, frame in enumerate(result.frames, start=1):
        print(
            f"[+] Frame {int(frame_index):02d}: "
            f"bits {int(frame.start_bit)}..{int(frame.end_bit)}, "
            f"destuff {int(frame.stuffed_bit_count)} -> "
            f"{int(frame.unstuffed_bit_count)} bits "
            f"(removed {int(frame.removed_stuffed_zeros)}), "
            f"FCS received=0x{int(frame.received_fcs):04X}, "
            f"calculated=0x{int(frame.calculated_fcs):04X} [OK]"
        )

    print(f"[+] Unique payloads    : {len(payloads)}")
    for payload_index, payload in enumerate(payloads, start=1):
        print(f"\n--- Payload {int(payload_index)} ---")
        print(payload.decode("ascii", errors="replace"), end="")
        if not payload.endswith(b"\n"):
            print()

    combined_payload: bytes = b"\n".join(payloads)
    if (
        b"CHANDELIER-7" in combined_payload
        and b"STATUS=GROUND CALIBRATION" in combined_payload
    ):
        print("\n[+] Interpretation")
        print("    -> CHANDELIER-7 calibration signal")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
