def calculate_tle_checksum(line):
    checksum = 0
    # 마지막 문자(X)를 제외한 앞부분까지만 계산
    for char in line[:-1]:
        if char.isdigit():
            checksum += int(char)  # 숫자는 해당 숫자값을 더함
        elif char == '-':
            checksum += 1          # -는 1을 더함
                                   # 나머지 문자는 0이므로 생략

    # 합계를 10으로 나눈 나머지 반환
    return str(checksum % 10)

def main():
    filename = 'corrupted_tles.txt'

    # 요구사항의 출력에 맞게 위성 이름을 치환하기 위한 매핑 딕셔너리
    name_mapping = {
        "ISS (ZARYA)": "ISS",
        "HUBBLE SPACE TELESCOPE": "HUBBLE",
        "NOAA 19": "NOAA 19",
        "LANDSAT 9": "LANDSAT 9",
        "STARLINK-31415": "STARLINK"
    }

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # 빈 줄을 제외하고 파일의 모든 줄을 읽어옴
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[-] '{filename}' 파일을 찾을 수 없습니다. 스크립트와 같은 경로에 파일을 만들어주세요.")
        return

    total_checksum_string = ""

    # 3줄씩(위성 이름, Line 1, Line 2) 그룹지어 처리
    for i in range(0, len(lines), 3):
        raw_name = lines[i]
        line1 = lines[i+1]
        line2 = lines[i+2]

        # 매핑된 이름이 있으면 가져오고, 없으면 원본 이름 사용
        display_name = name_mapping.get(raw_name, raw_name)

        chk1 = calculate_tle_checksum(line1)
        chk2 = calculate_tle_checksum(line2)

        total_checksum_string += chk1 + chk2

        # 위성 이름을 왼쪽 정렬하여 11칸을 차지하도록 포맷팅
        print(f"{display_name:<11}: {chk1} {chk2}")

    print("\n따라서 10자리 숫자는: " + total_checksum_string)
    print("\nSTARPWN{" + total_checksum_string + "}\n")

if __name__ == "__main__":
    main()
