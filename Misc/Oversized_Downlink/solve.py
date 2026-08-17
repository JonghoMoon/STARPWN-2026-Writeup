from PIL import Image
import re

def extract_lsb_r_channel(image_path):
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")
    except FileNotFoundError:
        print(f"[-] '{image_path}' 파일을 찾을 수 없습니다.")
        return

    width, height = img.size
    extracted_bits = ""

    # 1. 픽셀을 순회하며 오직 'R 채널'의 LSB(bit 0)만 추출
    for y in range(height):
        for x in range(width):
            r, _, _ = img.getpixel((x, y)) # G, B 값은 무시
            
            # R 채널의 최하위 비트만 추가
            extracted_bits += str(r & 1)

    # 2. 추출된 비트열을 8비트(1바이트) 단위로 묶어 문자로 변환
    extracted_text = ""
    for i in range(0, len(extracted_bits), 8):
        byte = extracted_bits[i:i+8]
        if len(byte) == 8:
            # 2진수 문자열을 문자로 디코딩 (깨진 문자 무시를 위해 예외 처리 추가 가능)
            extracted_text += chr(int(byte, 2))

    # 3. 결과 출력
    print("[+] R 채널 LSB 추출 완료!\n")
    
    print("--- 추출된 데이터 시작부 ---")
    print(extracted_text[:300]) 
    print("----------------------------\n")

    # 4. 플래그 포맷 탐색
    flag_pattern = re.compile(r'STARPWN\{.*?\}')
    flags_found = flag_pattern.findall(extracted_text)
    
    if flags_found:
        print(f"[!] 플래그 발견: {flags_found[0]}")
    else:
        print("[-] 평문은 복원되었으나 플래그를 찾지 못했습니다.")

# 스크립트 실행
if __name__ == "__main__":
    extract_lsb_r_channel("downlink.png")
