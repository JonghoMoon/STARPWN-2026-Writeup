import os
import io
import logging
import argparse
import ccsdspy
from ccsdspy.utils import split_by_apid
from scapy.all import rdpcap, UDP

# ccsdspy 내부 Warning 로그 차단
logging.getLogger("ccsdspy").setLevel(logging.ERROR)

# --- 1. 실행 인자 및 파일/환경 설정 ---
parser = argparse.ArgumentParser(
    description="PCAP에서 지정 APID의 CCSDS fragmented payload를 재조립합니다."
)
parser.add_argument(
    "apid",
    help="대상 APID. 10진수(예: 833) 또는 16진수(예: 0x341) 사용 가능"
)
args = parser.parse_args()

try:
    TARGET_APID = int(args.apid, 0)
except ValueError:
    parser.error(f"잘못된 APID 값입니다: {args.apid}")

if not (0 <= TARGET_APID <= 0x7FF):
    parser.error(f"CCSDS APID 범위를 벗어났습니다: 0x{TARGET_APID:X} (허용: 0x000~0x7FF)")

pcap_file = "spacecraft_capture.pcap"
temp_bin_file = "extracted_ccsds.bin"

# ⚠️ cFS 텔레메트리 세컨더리 헤더 기본 크기 설정 (시간 정보: 6바이트)
PRIMARY_HEADER_SIZE = 6
CFS_SECONDARY_HEADER_SIZE = 6
PACKET_PREFIX_SIZE = 2   # CA FE

print("📦 [1단계] PCAP에서 cFS CCSDS 바이너리 스트림 추출 중...")
packets = rdpcap(pcap_file)
ccsds_raw_data = bytearray()
for packet in packets:
    if packet.haslayer(UDP):
        ccsds_raw_data.extend(bytes(packet[UDP].payload))
with open(temp_bin_file, 'wb') as f:
    f.write(ccsds_raw_data)

print(f"📦 [2단계] APID별 분할 프로세스 가동 (Target: {TARGET_APID} / 0x{TARGET_APID:03X})...")
split_files = split_by_apid(temp_bin_file)

target_buffer = None
for apid_key in split_files.keys():
    if str(apid_key) == str(TARGET_APID):
        target_buffer = split_files[apid_key]
        break

if target_buffer is None:
    print(f"❌ 에러: APID {TARGET_APID} 데이터를 찾을 수 없습니다.")
    exit()

if isinstance(target_buffer, io.BytesIO):
    target_buffer.seek(0)
raw_bytes = target_buffer.read()

# --- 3. cFS 규격 가변 패킷 길이 분석 및 정확한 Fragmentation 필터링 ---
print(f"🚀 [3단계] cFS APID {TARGET_APID} (0x{TARGET_APID:03X}) 패킷 길이 정보 기반 정밀 스캔 시작...")

fragmented_payloads = bytearray()
packet_count = 0
pointer = 0
total_bytes = len(raw_bytes)

flag_names = {0: "중간 조각(Continuation)", 1: "첫 번째 조각(First)", 2: "마지막 조각(Last)"}

while pointer < total_bytes:
    # 최소 CCSDS 주 헤더(6바이트)가 없으면 종료
    if pointer + PRIMARY_HEADER_SIZE > total_bytes:
        break
        
    packet_header = raw_bytes[pointer : pointer + PRIMARY_HEADER_SIZE]
    
    # 1. 주 헤더 5, 6번째 바이트에서 패킷 크기 정보 파싱 (Big-Endian 규격)
    payload_length = ((packet_header[4] << 8) | packet_header[5]) + 1
    total_packet_size = PRIMARY_HEADER_SIZE + payload_length
    
    # 잔여 바이트 검증 에러 방지
    if pointer + total_packet_size > total_bytes:
        break
        
    full_packet = raw_bytes[pointer : pointer + total_packet_size]
    
    # 2. 주 헤더 3번째 바이트에서 Sequence Flags(상위 2비트) 추출
    seq_flags = (packet_header[2] & 0xC0) >> 6
    
    # 3. 시퀀스 카운트 추출 (나머지 14비트)
    seq_count = ((packet_header[2] & 0x3F) << 8) | packet_header[3]
    
    # 분할 패킷(Flags가 3이 아닌 경우)만 정확히 걸러내기
    if seq_flags != 3:
        packet_count += 1
        
        # ⚠️ cFS 핵심: 주 헤더(6B)와 cFS 세컨더리 헤더(6B)를 모두 도려낸 순수 데이터 슬라이싱
        header_offset = PRIMARY_HEADER_SIZE + CFS_SECONDARY_HEADER_SIZE + PACKET_PREFIX_SIZE
        pure_payload = full_packet[header_offset:]
        fragmented_payloads.extend(pure_payload)
        
        print(f"🚨 cFS 분할 패킷! [번호: #{packet_count}] 순서번호(Seq): {seq_count} | 패킷 전체크기: {total_packet_size} 바이트 | 종류: {flag_names.get(seq_flags)}")

    # 다음 패킷으로 포인터 점프
    pointer += total_packet_size

# --- 4. 추출된 분할 페이로드 파일 저장 ---
if packet_count > 0:
    output_bin = f"fragmented_payload_{TARGET_APID:03X}.bin"
    with open(output_bin, 'wb') as f:
        f.write(fragmented_payloads)
    print(f"\n💾 [추출 완료] cFS 규격의 진짜 분할 패킷 {packet_count}개를 병합하여 '{output_bin}' 파일로 저장했습니다.")
else:
    print("\n✅ cFS 규격 정밀 스캔 결과, APID 833 패킷 중 분할 전송(Fragmentation)된 패킷이 없습니다.")

