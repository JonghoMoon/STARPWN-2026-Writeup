#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

REPORT_TIME_FORMAT = "%d %b %Y %H:%M:%S.%f"
INFECTION_TIME_FORMAT = "%d %b %Y %H:%M:%S"

# The challenge explicitly limits the analysis to this four-hour window.
ANALYSIS_START = datetime(2026, 4, 24, 20, 0, 0)
ANALYSIS_STOP = datetime(2026, 4, 25, 0, 0, 0)

DEFAULT_EXPECTED_COUNT = 4
DEFAULT_FLAG_PREFIX = "450"
DEFAULT_SLOT_PREFIXES = ("12", "11", "13", "12")

SECTION_RE = re.compile(
    r"^GCS(?P<gcs>\d+)-To-CubeSat(?P<satellite>\d+)\s*$"
)
ACCESS_RE = re.compile(
    r"^\s*(?P<index>\d+)\s+"
    r"(?P<start>\d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<stop>\d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<duration>\d+(?:\.\d+)?)\s*$"
)
INFECTION_RE = re.compile(
    r"^(?P<gcs>GCS\d+)\s+around\s+"
    r"(?P<time>\d{2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2})\s*$"
)
VALID_SATELLITE_RE = re.compile(r"^SAT\d{4}$")


@dataclass(frozen=True)
class AccessWindow:
    gcs: str
    satellite: str
    start: datetime
    stop: datetime
    duration_seconds: float

    def contains(self, instant: datetime) -> bool:
        # STK access intervals are treated as start-inclusive and stop-exclusive.
        return bool(self.start <= instant < self.stop)


def parse_datetime(value: str, date_format: str) -> datetime:
    return datetime.strptime(str(value), str(date_format))


def parse_infection_times(path: Path) -> dict[str, datetime]:
    infection_times: dict[str, datetime] = {}

    for raw_line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = str(raw_line).strip()
        match = INFECTION_RE.match(line)
        if match is None:
            continue

        gcs = str(match.group("gcs"))
        instant = parse_datetime(str(match.group("time")), INFECTION_TIME_FORMAT)
        infection_times[gcs] = instant

    if not infection_times:
        raise ValueError(f"No infection times were parsed from: {path}")

    return infection_times


def parse_access_report(path: Path, expected_gcs: str) -> list[AccessWindow]:
    windows: list[AccessWindow] = []
    current_gcs: str | None = None
    current_satellite: str | None = None

    for raw_line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = str(raw_line).rstrip()

        section_match = SECTION_RE.match(line)
        if section_match is not None:
            section_gcs = f"GCS{int(section_match.group('gcs'))}"
            satellite_id = str(section_match.group("satellite"))
            satellite = f"SAT{satellite_id}"

            current_gcs = str(section_gcs)
            current_satellite = str(satellite)
            continue

        access_match = ACCESS_RE.match(line)
        if access_match is None:
            continue
        if current_gcs is None or current_satellite is None:
            continue
        if current_gcs != expected_gcs:
            continue

        # CubeSat1 is an alias/duplicate entry and is not a four-digit challenge ID.
        if VALID_SATELLITE_RE.fullmatch(current_satellite) is None:
            continue

        start = parse_datetime(str(access_match.group("start")), REPORT_TIME_FORMAT)
        stop = parse_datetime(str(access_match.group("stop")), REPORT_TIME_FORMAT)
        duration_seconds = float(access_match.group("duration"))

        windows.append(
            AccessWindow(
                gcs=str(current_gcs),
                satellite=str(current_satellite),
                start=start,
                stop=stop,
                duration_seconds=float(duration_seconds),
            )
        )

    if not windows:
        raise ValueError(f"No satellite access windows were parsed from: {path}")

    return windows


def locate_infection_file(directory: Path) -> Path:
    matches = sorted(directory.glob("Ground Station Infection Times*.txt"))
    if len(matches) != 1:
        names = ", ".join(str(path.name) for path in matches) or "none"
        raise FileNotFoundError(
            "Expected exactly one 'Ground Station Infection Times*.txt' file "
            f"in {directory}; found: {names}"
        )
    return matches[0]


def locate_report_file(directory: Path, gcs: str) -> Path:
    gcs_number = int(gcs.removeprefix("GCS"))
    exact_path = directory / f"GCS{gcs_number}.txt"
    if exact_path.is_file():
        return exact_path

    matches = sorted(directory.glob(f"GCS{gcs_number}*.txt"))
    if len(matches) != 1:
        names = ", ".join(str(path.name) for path in matches) or "none"
        raise FileNotFoundError(
            f"Expected exactly one report for {gcs} in {directory}; found: {names}"
        )
    return matches[0]


def find_simultaneous_accesses(
    infection_time: datetime,
    windows: Sequence[AccessWindow],
) -> list[AccessWindow]:
    by_satellite: dict[str, AccessWindow] = {}

    for window in windows:
        if window.contains(infection_time):
            by_satellite[str(window.satellite)] = window

    return sorted(
        by_satellite.values(),
        key=lambda item: (item.start, item.satellite),
    )


def parse_slot_prefixes(value: str) -> tuple[str, ...]:
    prefixes = tuple(str(part).strip() for part in str(value).split(","))
    if not prefixes or any(not prefix.isdigit() for prefix in prefixes):
        raise argparse.ArgumentTypeError(
            "The order must be comma-separated numeric prefixes, for example: 12,11,13,12"
        )
    return prefixes


def order_satellites(
    accesses: Sequence[AccessWindow],
    slot_prefixes: Sequence[str],
) -> list[str]:
    grouped: dict[str, list[AccessWindow]] = {}

    for access in accesses:
        satellite_id = str(access.satellite).removeprefix("SAT")
        prefix = str(satellite_id[:2])
        grouped.setdefault(prefix, []).append(access)

    for prefix in grouped:
        grouped[prefix].sort(key=lambda item: (item.start, item.satellite))

    ordered: list[str] = []
    for raw_prefix in slot_prefixes:
        prefix = str(raw_prefix)
        candidates = grouped.get(prefix, [])
        if not candidates:
            available = ", ".join(
                f"{key}:{len(value)}" for key, value in sorted(grouped.items())
            )
            raise ValueError(
                f"Cannot fill flag slot prefix {prefix}; available groups: {available}"
            )

        selected = candidates.pop(0)
        ordered.append(str(selected.satellite))

    leftovers = [
        access.satellite
        for values in grouped.values()
        for access in values
    ]
    if leftovers:
        raise ValueError(
            "The slot order did not consume every selected satellite: "
            + ", ".join(str(value) for value in leftovers)
        )

    return ordered


def build_argument_parser() -> argparse.ArgumentParser:
    script_directory = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description=(
            "Extract the Silent Horizon infected satellites from the STK access reports."
        )
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=script_directory,
        help="Directory containing GCS1.txt through GCS4.txt and the infection-time file.",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=int(DEFAULT_EXPECTED_COUNT),
        help="Expected number of simultaneously infected satellites.",
    )
    parser.add_argument(
        "--order",
        type=parse_slot_prefixes,
        default=DEFAULT_SLOT_PREFIXES,
        help="Flag satellite-prefix order. Default: 12,11,13,12",
    )
    parser.add_argument(
        "--flag-prefix",
        type=str,
        default=str(DEFAULT_FLAG_PREFIX),
        help="Numeric value placed after 'STARPWN{'. Default: 450",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the final flag.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    directory = Path(args.directory).expanduser().resolve()
    expected_count = int(args.expected_count)
    slot_prefixes = tuple(str(value) for value in args.order)
    flag_prefix = str(args.flag_prefix)
    quiet = bool(args.quiet)

    if expected_count <= 0:
        parser.error("--expected-count must be greater than zero")
    if len(slot_prefixes) != expected_count:
        parser.error(
            "The number of --order slots must equal --expected-count "
            f"({len(slot_prefixes)} != {expected_count})"
        )
    if not directory.is_dir():
        parser.error(f"Not a directory: {directory}")

    infection_file = locate_infection_file(directory)
    infection_times = parse_infection_times(infection_file)

    events: list[tuple[str, datetime, list[AccessWindow]]] = []

    for gcs in sorted(infection_times, key=lambda value: int(value.removeprefix("GCS"))):
        infection_time = infection_times[gcs]

        # Ignore infection timestamps outside the time range specified by the challenge.
        if not (ANALYSIS_START <= infection_time < ANALYSIS_STOP):
            continue

        report_file = locate_report_file(directory, gcs)
        windows = parse_access_report(report_file, expected_gcs=str(gcs))
        simultaneous = find_simultaneous_accesses(infection_time, windows)
        events.append((str(gcs), infection_time, simultaneous))

    matching_events = [
        event for event in events if len(event[2]) == expected_count
    ]

    if len(matching_events) != 1:
        summary = "; ".join(
            f"{gcs}={len(accesses)}" for gcs, _, accesses in events
        )
        raise RuntimeError(
            "Expected exactly one infection event with "
            f"{expected_count} simultaneous satellite accesses; found "
            f"{len(matching_events)}. Counts: {summary}"
        )

    selected_gcs, selected_time, selected_accesses = matching_events[0]
    ordered_satellites = order_satellites(selected_accesses, slot_prefixes)
    flag = f"STARPWN{{{flag_prefix}:{''.join(ordered_satellites)}!}}"

    if quiet:
        print(flag)
        return int(0)

    print("[*] Satellites connected at each GCS infection time")
    for gcs, infection_time, accesses in events:
        satellite_list = ", ".join(access.satellite for access in accesses) or "none"
        print(
            f"    {gcs} @ {infection_time.strftime(INFECTION_TIME_FORMAT)} "
            f"-> {len(accesses)}: {satellite_list}"
        )

    print(
        f"[+] Selected event: {selected_gcs} @ "
        f"{selected_time.strftime(INFECTION_TIME_FORMAT)}"
    )
    for access in selected_accesses:
        print(
            "    "
            f"{access.satellite}: "
            f"{access.start.strftime(REPORT_TIME_FORMAT)} -> "
            f"{access.stop.strftime(REPORT_TIME_FORMAT)}"
        )

    print(f"[+] Slot order: {','.join(slot_prefixes)}")
    print(f"[+] Flag: {flag}")
    return int(0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"[-] {error}", file=sys.stderr)
        raise SystemExit(int(1))
