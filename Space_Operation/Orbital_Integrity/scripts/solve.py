def calculate_tle_checksum(line):
    checksum = 0
    # Calculate using all characters except the final checksum character
    for char in line[:-1]:
        if char.isdigit():
            checksum += int(char)  # Add the numeric value of each digit
        elif char == '-':
            checksum += 1          # A minus sign contributes 1
                                   # All other characters contribute 0

    # Return the sum modulo 10
    return str(checksum % 10)

def main():
    filename = 'corrupted_tles.txt'

    # Map satellite names to the format used in the expected output
    name_mapping = {
        "ISS (ZARYA)": "ISS",
        "HUBBLE SPACE TELESCOPE": "HUBBLE",
        "NOAA 19": "NOAA 19",
        "LANDSAT 9": "LANDSAT 9",
        "STARLINK-31415": "STARLINK"
    }

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            # Read all non-empty lines from the file
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"[-] File not found: '{filename}'. Place the file in the same directory as this script.")
        return

    total_checksum_string = ""

    # Process the input in groups of three lines: satellite name, TLE line 1, and TLE line 2
    for i in range(0, len(lines), 3):
        raw_name = lines[i]
        line1 = lines[i+1]
        line2 = lines[i+2]

        # Use the mapped display name if available; otherwise keep the original name
        display_name = name_mapping.get(raw_name, raw_name)

        chk1 = calculate_tle_checksum(line1)
        chk2 = calculate_tle_checksum(line2)

        total_checksum_string += chk1 + chk2

        # Left-align the satellite name in an 11-character field
        print(f"{display_name:<11}: {chk1} {chk2}")

    print("\nThe resulting 10-digit number is: " + total_checksum_string)
    print("\nSTARPWN{" + total_checksum_string + "}\n")

if __name__ == "__main__":
    main()
