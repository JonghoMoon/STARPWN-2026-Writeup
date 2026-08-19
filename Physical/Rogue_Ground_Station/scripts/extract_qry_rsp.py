#!/usr/bin/env python3

import argparse
import struct
from collections import defaultdict


PCAP_MAGIC_LE_USEC = b"\xd4\xc3\xb2\xa1"
PCAP_MAGIC_BE_USEC = b"\xa1\xb2\xc3\xd4"
PCAP_MAGIC_LE_NSEC = b"\x4d\x3c\xb2\xa1"
PCAP_MAGIC_BE_NSEC = b"\xa1\xb2\x3c\x4d"

CCSDS_PRIMARY_HEADER_SIZE = 6
CFS_SECONDARY_HEADER_SIZE = 6
PACKET_PREFIX_SIZE = 2          # CA FE
APP_HEADER_SIZE = 12            # QRY1 + ID + Length + 4-byte field


def iter_pcap(path):
    """
    Minimal classic-PCAP reader.

    Yields:
        (packet_index, timestamp, linktype, captured_bytes)
    """
    with open(path, "rb") as fp:
        global_header = fp.read(24)

        if len(global_header) != 24:
            raise RuntimeError("Invalid PCAP global header")

        magic = global_header[:4]

        if magic == PCAP_MAGIC_LE_USEC:
            endian = "<"
            scale = 1_000_000
        elif magic == PCAP_MAGIC_BE_USEC:
            endian = ">"
            scale = 1_000_000
        elif magic == PCAP_MAGIC_LE_NSEC:
            endian = "<"
            scale = 1_000_000_000
        elif magic == PCAP_MAGIC_BE_NSEC:
            endian = ">"
            scale = 1_000_000_000
        else:
            raise RuntimeError("Unsupported PCAP format")

        _, _, _, _, _, _, linktype = struct.unpack(
            endian + "IHHIIII",
            global_header,
        )

        packet_index = 0

        while True:
            packet_header = fp.read(16)

            if not packet_header:
                break

            if len(packet_header) != 16:
                raise RuntimeError("Truncated PCAP packet header")

            ts_sec, ts_frac, incl_len, _ = struct.unpack(
                endian + "IIII",
                packet_header,
            )

            packet = fp.read(incl_len)

            if len(packet) != incl_len:
                raise RuntimeError("Truncated PCAP packet")

            packet_index += 1
            timestamp = ts_sec + (ts_frac / scale)

            yield packet_index, timestamp, linktype, packet


def extract_ipv4(packet, linktype):
    """
    Return the IPv4 packet from the PCAP record.

    Supports:
      DLT_RAW      = 101 / 228 depending on producer/platform
      DLT_IPV4     = 228
      Ethernet     = 1
    """
    if not packet:
        return None

    # Raw IPv4 capture
    if (packet[0] >> 4) == 4:
        return packet

    # Ethernet
    if linktype == 1 and len(packet) >= 14:
        ethertype = struct.unpack("!H", packet[12:14])[0]

        if ethertype == 0x0800:
            return packet[14:]

    return None


def extract_udp_payload(ip_packet):
    if ip_packet is None or len(ip_packet) < 20:
        return None

    version = ip_packet[0] >> 4
    ihl = (ip_packet[0] & 0x0F) * 4

    if version != 4 or ihl < 20:
        return None

    if len(ip_packet) < ihl + 8:
        return None

    # IPv4 protocol 17 = UDP
    if ip_packet[9] != 17:
        return None

    udp_length = struct.unpack("!H", ip_packet[ihl + 4:ihl + 6])[0]

    if udp_length < 8:
        return None

    return ip_packet[ihl + 8:ihl + udp_length]


def parse_ccsds(udp_payload, packet_index, timestamp):
    if udp_payload is None or len(udp_payload) < CCSDS_PRIMARY_HEADER_SIZE:
        return None

    packet_id = struct.unpack("!H", udp_payload[0:2])[0]
    seq_control = struct.unpack("!H", udp_payload[2:4])[0]
    packet_length = struct.unpack("!H", udp_payload[4:6])[0] + 1

    total_size = CCSDS_PRIMARY_HEADER_SIZE + packet_length

    if len(udp_payload) < total_size:
        return None

    packet = udp_payload[:total_size]

    apid = packet_id & 0x07FF
    seq_flags = (seq_control >> 14) & 0x03
    seq_count = seq_control & 0x3FFF

    minimum = (
        CCSDS_PRIMARY_HEADER_SIZE
        + CFS_SECONDARY_HEADER_SIZE
        + PACKET_PREFIX_SIZE
    )

    if len(packet) < minimum:
        return None

    secondary = packet[
        CCSDS_PRIMARY_HEADER_SIZE:
        CCSDS_PRIMARY_HEADER_SIZE + CFS_SECONDARY_HEADER_SIZE
    ]

    prefix_offset = (
        CCSDS_PRIMARY_HEADER_SIZE
        + CFS_SECONDARY_HEADER_SIZE
    )

    prefix = packet[
        prefix_offset:
        prefix_offset + PACKET_PREFIX_SIZE
    ]

    app_data = packet[
        prefix_offset + PACKET_PREFIX_SIZE:
    ]

    return {
        "packet_index": packet_index,
        "timestamp": timestamp,
        "apid": apid,
        "seq_flags": seq_flags,
        "seq_count": seq_count,
        "secondary": secondary,
        "prefix": prefix,
        "app_data": app_data,
    }


def load_ccsds_packets(path):
    records = []

    for packet_index, timestamp, linktype, packet in iter_pcap(path):
        ip_packet = extract_ipv4(packet, linktype)
        udp_payload = extract_udp_payload(ip_packet)

        ccsds = parse_ccsds(
            udp_payload,
            packet_index,
            timestamp,
        )

        if ccsds is not None:
            records.append(ccsds)

    return records


def reassemble_fragmented(records):
    """
    CCSDS sequence flags:
        0 = continuation
        1 = first
        2 = last
        3 = unsegmented

    The cFS secondary header and CA FE prefix are present in each
    fragment, so only app_data is concatenated.
    """
    active = {}
    complete = []

    for record in records:
        apid = record["apid"]
        flag = record["seq_flags"]

        if flag == 1:
            active[apid] = {
                "apid": apid,
                "timestamp": record["timestamp"],
                "first_packet": record["packet_index"],
                "secondary": record["secondary"],
                "chunks": [record["app_data"]],
            }

        elif flag == 0:
            if apid in active:
                active[apid]["chunks"].append(record["app_data"])

        elif flag == 2:
            if apid in active:
                active[apid]["chunks"].append(record["app_data"])

                assembly = active.pop(apid)
                assembly["payload"] = b"".join(assembly["chunks"])
                complete.append(assembly)

    return complete


def parse_qry1(payload):
    if not payload.startswith(b"QRY1"):
        return None

    if len(payload) < APP_HEADER_SIZE:
        return None

    query_id = struct.unpack("!H", payload[4:6])[0]
    declared_length = struct.unpack("!H", payload[6:8])[0]

    # This is the 4-byte value shown as "Correlation Field" in the table.
    correlation_field = payload[8:12]

    body = payload[12:]

    return {
        "id": query_id,
        "length": declared_length,
        "correlation_field": correlation_field,
        "body": body,
        "length_valid": declared_length == len(body),
    }


def collect_queries(records):
    queries = []

    # Fragmented QRY1 messages
    for assembly in reassemble_fragmented(records):
        parsed = parse_qry1(assembly["payload"])

        if parsed is None:
            continue

        queries.append({
            "timestamp": assembly["timestamp"],
            "packet_index": assembly["first_packet"],
            "apid": assembly["apid"],
            "secondary": assembly["secondary"],
            **parsed,
        })

    # Also support unsegmented QRY1 messages.
    for record in records:
        if record["seq_flags"] != 3:
            continue

        parsed = parse_qry1(record["app_data"])

        if parsed is None:
            continue

        queries.append({
            "timestamp": record["timestamp"],
            "packet_index": record["packet_index"],
            "apid": record["apid"],
            "secondary": record["secondary"],
            **parsed,
        })

    queries.sort(key=lambda x: x["timestamp"])

    return queries


def collect_responses(records):
    responses = []

    for record in records:
        payload = record["app_data"]

        if not payload.startswith(b"RSP1"):
            continue

        response_bytes = payload[4:]

        try:
            message = response_bytes.decode("ascii")
        except UnicodeDecodeError:
            message = response_bytes.hex()

        responses.append({
            "timestamp": record["timestamp"],
            "packet_index": record["packet_index"],
            "apid": record["apid"],
            "secondary": record["secondary"],
            "message": message,
        })

    responses.sort(key=lambda x: x["timestamp"])

    return responses


def pair_queries_and_responses(queries, responses):
    """
    Pair using:
      1. same APID
      2. same low-byte query identifier in the cFS secondary header
      3. response must occur after the query

    Observed secondary-header convention in this capture:
        QRY1: ... 0x51 <ID-low-byte>
        RSP1: ... 0x52 <ID-low-byte>
    """
    by_apid = defaultdict(list)

    for response in responses:
        by_apid[response["apid"]].append(response)

    pairs = []

    for query in queries:
        candidates = []

        query_id_low = query["id"] & 0xFF

        for response in by_apid[query["apid"]]:
            if response["timestamp"] < query["timestamp"]:
                continue

            secondary = response["secondary"]

            if len(secondary) >= 6 and secondary[-1] == query_id_low:
                candidates.append(response)

        response = min(
            candidates,
            key=lambda x: x["timestamp"],
            default=None,
        )

        pairs.append((query, response))

    return pairs


def print_table(pairs):
    print()

    print(
        f"| {'APID':<6} "
        f"| {'RSP1 Response':<13} "
        f"| {'Correlation Field (4B)':<22} |"
    )

    print(
        f"|{'-' * 8}"
        f"|{'-' * 15}"
        f"|{'-' * 24}|"
    )

    for query, response in pairs:
        rsp = response["message"] if response else "<not found>"

        apid = f"0x{query['apid']:03X}"
        correlation = query["correlation_field"].hex()

        print(
            f"| {apid:<6} "
            f"| {rsp:<13} "
            f"| {correlation:<22} |"
        )

    print()


def print_verbose(pairs):
    for query, response in pairs:
        print("=" * 68)
        print(f"APID              : 0x{query['apid']:03X}")
        print(f"QRY packet        : #{query['packet_index']}")
        print(f"QRY ID            : 0x{query['id']:04X}")
        print(f"QRY Length        : {query['length']}")
        print(f"Length check      : {'OK' if query['length_valid'] else 'FAIL'}")
        print(
            "Correlation Field : "
            f"{query['correlation_field'].hex()}"
        )

        if response is None:
            print("RSP1              : <not found>")
        else:
            print(f"RSP packet        : #{response['packet_index']}")
            print(f"RSP1              : {response['message']}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Extract QRY1/RSP1 pairs from the Rogue Ground Station PCAP."
        )
    )

    parser.add_argument(
        "pcap",
        nargs="?",
        default="spacecraft_capture.pcap",
        help="input PCAP file (default: spacecraft_capture.pcap)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show detailed QRY1/RSP1 information",
    )

    args = parser.parse_args()

    records = load_ccsds_packets(args.pcap)
    queries = collect_queries(records)
    responses = collect_responses(records)

    pairs = pair_queries_and_responses(
        queries,
        responses,
    )

    print(f"[+] CCSDS packets : {len(records)}")
    print(f"[+] QRY1 messages : {len(queries)}")
    print(f"[+] RSP1 messages : {len(responses)}")
    print(f"[+] Matched pairs : {sum(r is not None for _, r in pairs)}")

    if args.verbose:
        print()
        print_verbose(pairs)

    print_table(pairs)


if __name__ == "__main__":
    main()
