from PIL import Image
import re

def extract_lsb_r_channel(image_path):
    try:
        img = Image.open(image_path)
        img = img.convert("RGB")
    except FileNotFoundError:
        print(f"[-] File not found: '{image_path}'")
        return

    width, height = img.size
    extracted_bits = ""

    # 1. Iterate over all pixels and extract only the LSB (bit 0) of the R channel
    for y in range(height):
        for x in range(width):
            r, _, _ = img.getpixel((x, y))  # Ignore the G and B channels
            
            # Append only the least significant bit of the R channel
            extracted_bits += str(r & 1)

    # 2. Group the extracted bitstream into 8-bit bytes and convert them to characters
    extracted_text = ""
    for i in range(0, len(extracted_bits), 8):
        byte = extracted_bits[i:i+8]
        if len(byte) == 8:
            # Decode the binary string as a character
            extracted_text += chr(int(byte, 2))

    # 3. Print the extracted data
    print("[+] R-channel LSB extraction complete!\n")
    
    print("--- Beginning of extracted data ---")
    print(extracted_text[:300]) 
    print("----------------------------\n")

    # 4. Search for the flag pattern
    flag_pattern = re.compile(r'STARPWN\{.*?\}')
    flags_found = flag_pattern.findall(extracted_text)
    
    if flags_found:
        print(f"[!] Flag found: {flags_found[0]}")
    else:
        print("[-] Plaintext was recovered, but no flag was found.")

# Run the script
if __name__ == "__main__":
    extract_lsb_r_channel("downlink.png")
