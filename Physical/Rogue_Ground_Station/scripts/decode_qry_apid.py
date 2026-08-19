import os
import io
import logging
import argparse
import ccsdspy
from ccsdspy.utils import split_by_apid
from scapy.all import rdpcap, UDP

# Suppress internal ccsdspy warning messages
logging.getLogger("ccsdspy").setLevel(logging.ERROR)

# --- 1. Command-line arguments and file/environment setup ---
parser = argparse.ArgumentParser(
    description="Reassemble fragmented CCSDS payloads for a specified APID from a PCAP file."
)
parser.add_argument(
    "apid",
    help="Target APID. Decimal (e.g. 833) or hexadecimal (e.g. 0x341) is accepted."
)
args = parser.parse_args()

try:
    TARGET_APID = int(args.apid, 0)
except ValueError:
    parser.error(f"Invalid APID value: {args.apid}")

if not (0 <= TARGET_APID <= 0x7FF):
    parser.error(f"APID is outside the CCSDS range: 0x{TARGET_APID:X} (valid: 0x000-0x7FF)")

pcap_file = "spacecraft_capture.pcap"
temp_bin_file = "extracted_ccsds.bin"

# cFS telemetry header sizes (secondary header contains 6 bytes of time information)
PRIMARY_HEADER_SIZE = 6
CFS_SECONDARY_HEADER_SIZE = 6
PACKET_PREFIX_SIZE = 2   # CA FE

print("[1] Extracting the cFS CCSDS binary stream from the PCAP...")
packets = rdpcap(pcap_file)
ccsds_raw_data = bytearray()
for packet in packets:
    if packet.haslayer(UDP):
        ccsds_raw_data.extend(bytes(packet[UDP].payload))
with open(temp_bin_file, 'wb') as f:
    f.write(ccsds_raw_data)

print(f"[2] Splitting CCSDS packets by APID (Target: {TARGET_APID} / 0x{TARGET_APID:03X})...")
split_files = split_by_apid(temp_bin_file)

target_buffer = None
for apid_key in split_files.keys():
    if str(apid_key) == str(TARGET_APID):
        target_buffer = split_files[apid_key]
        break

if target_buffer is None:
    print(f"[!] Error: No data found for APID {TARGET_APID}.")
    exit()

if isinstance(target_buffer, io.BytesIO):
    target_buffer.seek(0)
raw_bytes = target_buffer.read()

# --- 3. Parse variable-length cFS packets and filter fragmented packets ---
print(f"[3] Scanning cFS APID {TARGET_APID} (0x{TARGET_APID:03X}) using packet-length information...")

fragmented_payloads = bytearray()
packet_count = 0
pointer = 0
total_bytes = len(raw_bytes)

flag_names = {0: "Continuation", 1: "First", 2: "Last"}

while pointer < total_bytes:
    # Stop if fewer than 6 bytes remain for a CCSDS primary header
    if pointer + PRIMARY_HEADER_SIZE > total_bytes:
        break
        
    packet_header = raw_bytes[pointer : pointer + PRIMARY_HEADER_SIZE]
    
    # 1. Parse packet length from bytes 5-6 of the primary header (big-endian)
    payload_length = ((packet_header[4] << 8) | packet_header[5]) + 1
    total_packet_size = PRIMARY_HEADER_SIZE + payload_length
    
    # Stop if the remaining data is shorter than the declared packet size
    if pointer + total_packet_size > total_bytes:
        break
        
    full_packet = raw_bytes[pointer : pointer + total_packet_size]
    
    # 2. Extract Sequence Flags from the upper two bits of byte 3
    seq_flags = (packet_header[2] & 0xC0) >> 6
    
    # 3. Extract the 14-bit sequence count
    seq_count = ((packet_header[2] & 0x3F) << 8) | packet_header[3]
    
    # Keep only segmented packets (Sequence Flags != 3)
    if seq_flags != 3:
        packet_count += 1
        
        # Strip the 6-byte CCSDS primary header, 6-byte cFS secondary header, and 2-byte CA FE prefix
        header_offset = PRIMARY_HEADER_SIZE + CFS_SECONDARY_HEADER_SIZE + PACKET_PREFIX_SIZE
        pure_payload = full_packet[header_offset:]
        fragmented_payloads.extend(pure_payload)
        
        print(f"[+] Fragment #{packet_count} | Seq: {seq_count} | Packet size: {total_packet_size} bytes | Type: {flag_names.get(seq_flags)}")

    # Advance to the next packet
    pointer += total_packet_size

# --- 4. Save the reassembled fragmented payload ---
if packet_count > 0:
    output_bin = f"apid_{TARGET_APID:03X}_QRY1_payload.bin"
    with open(output_bin, 'wb') as f:
        f.write(fragmented_payloads)
    print(f"\n[+] Reassembled {packet_count} fragmented cFS packets and saved the payload to '{output_bin}'.")
else:
    print(f"\n[-] No fragmented packets found for APID {TARGET_APID} during the cFS scan.")

