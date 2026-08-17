"""
CTF Beacon WAV - CW Morse Decoder
Decodes 12 WPM Morse code on a 600 Hz tone and extracts the flag.

Usage:
    python3 beacon_decode.py [path/to/beacon.wav]
"""

import sys
import wave
import numpy as np
from scipy.signal import butter, filtfilt, hilbert
from scipy.ndimage import uniform_filter1d


# ── Morse lookup table ────────────────────────────────────────────────────────
MORSE_MAP = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z',
    '-----': '0', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
}


def load_wav(path: str):
    with wave.open(path) as w:
        frames = w.readframes(w.getnframes())
        sr = w.getframerate()
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sr


def bandpass(data: np.ndarray, low: float, high: float, fs: int) -> np.ndarray:
    """4th-order Butterworth bandpass filter."""
    b, a = butter(4, [low / (fs / 2), high / (fs / 2)], btype='band')
    return filtfilt(b, a, data)


def detect_segments(samples: np.ndarray, sr: int,
                    tone_hz: float = 600.0,
                    bw: float = 200.0,
                    smooth_ms: float = 10.0,
                    threshold_ratio: float = 0.3):
    """Return list of (start_sample, end_sample) for each ON segment."""
    filtered  = bandpass(samples, tone_hz - bw / 2, tone_hz + bw / 2, sr)
    envelope  = np.abs(hilbert(filtered))
    smooth    = uniform_filter1d(envelope, size=int(sr * smooth_ms / 1000))
    threshold = smooth.max() * threshold_ratio
    on        = smooth > threshold

    trans  = np.diff(on.astype(np.int8))
    starts = np.where(trans == 1)[0]
    ends   = np.where(trans == -1)[0]

    if on[0]:  starts = np.r_[0, starts]
    if on[-1]: ends   = np.r_[ends, len(on) - 1]

    return list(zip(starts, ends))


def segments_to_morse_words(segments: list, sr: int,
                             dit_ms: float = 100.0) -> list[str]:
    """
    Convert tone segments to a list of decoded words.

    Timing at 12 WPM:
        dit  ≈ 100 ms
        dah  ≈ 300 ms   (> 2× dit)
        char gap ≈ 300 ms   (> 2× dit between chars)
        word gap ≈ 700 ms   (> 5× dit between words)
    """
    dah_thresh  = dit_ms * 2   # ms  — tone longer than this → dah
    char_thresh = dit_ms * 2   # ms  — gap longer than this  → new char
    word_thresh = dit_ms * 5   # ms  — gap longer than this  → new word

    # Build symbol sequence
    syms = []
    for i, (s, e) in enumerate(segments):
        dur_ms = (e - s) / sr * 1000
        syms.append('dah' if dur_ms > dah_thresh else 'dit')

        if i < len(segments) - 1:
            gap_ms = (segments[i + 1][0] - e) / sr * 1000
            if gap_ms > word_thresh:
                syms.append('WORD')
            elif gap_ms > char_thresh:
                syms.append('CHAR')
            # intra-character gap → nothing

    # Decode symbols → words
    words: list[str] = []
    current_word: list[str] = []
    current_morse = ''

    def flush_char():
        nonlocal current_morse
        if current_morse:
            current_word.append(MORSE_MAP.get(current_morse, f'?{current_morse}?'))
            current_morse = ''

    def flush_word():
        flush_char()
        if current_word:
            words.append(''.join(current_word))
            current_word.clear()

    for sym in syms:
        if   sym == 'dit':  current_morse += '.'
        elif sym == 'dah':  current_morse += '-'
        elif sym == 'CHAR': flush_char()
        elif sym == 'WORD': flush_word()

    flush_word()
    return words


def extract_flag(words: list[str]) -> str:
    """
    Amateur CW format:
        VVV VVV VVV DE <callsign×3> <payload — four words> 73 DE <callsign> K
    The four payload words come right after the third callsign block.
    """
    # Find the end of the "VVV VVV VVV DE CALL CALL CALL" preamble
    # Strategy: skip past the last group of 3 identical callsigns before the payload
    i = 0
    # Skip VVV groups and DE
    while i < len(words) and words[i] in ('VVV', 'DE'):
        i += 1
    # Skip callsign × 3
    if i < len(words):
        callsign = words[i]
        while i < len(words) and words[i] == callsign:
            i += 1
    # Next four words are the payload
    payload = words[i:i + 4]
    return 'STARPWN{' + '_'.join(payload) + '}'


def main(wav_path: str):
    print(f"[*] Loading {wav_path}")
    samples, sr = load_wav(wav_path)
    print(f"    sample rate: {sr} Hz  |  duration: {len(samples)/sr:.1f} s")

    print("[*] Detecting 600 Hz tone segments …")
    segs = detect_segments(samples, sr)
    print(f"    found {len(segs)} tone segments")

    print("[*] Decoding Morse …")
    words = segments_to_morse_words(segs, sr)
    print(f"    message: {' '.join(words)}")

    flag = extract_flag(words)
    print(f"\n[+] FLAG: {flag}")
    return flag


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'beacon.wav'
    main(path)
