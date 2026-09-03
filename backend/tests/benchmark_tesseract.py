"""
Benchmarks Tesseract (chi_tra, best-accuracy tessdata) against known text,
on both synthetic fixtures and real cropped subtitle frames pulled from the
cached real video clip (same source that exposed RapidOCR's accuracy
regression), logging timing for each.

    .venv/Scripts/python -m backend.tests.benchmark_tesseract
"""

import os
import time
from pathlib import Path

os.environ["TESSDATA_PREFIX"] = str(Path(__file__).resolve().parents[1] / "tessdata")

import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from backend.services.frames import extract_frames

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CACHE_DIR = Path(os.environ.get("TEMP", "C:/Windows/Temp")) / "ytt_realcheck_cache"

FIXTURE_EXPECTED = {
    "greeting.jpg": "你好",
    "question.jpg": "這是什麼意思",
    "mixed.jpg": "再見",
}

# Real subtitle lines at these timestamps, verified earlier in this session
# via EasyOCR + manual cross-check against the video.
REAL_EXPECTED = {
    0: "定弘這三年來",
    46: "對老人家永遠的懷念和哀思",
}


def ocr_image(path, psm=7):
    t0 = time.monotonic()
    text = pytesseract.image_to_string(str(path), lang="chi_tra", config=f"--psm {psm}")
    elapsed = time.monotonic() - t0
    return text.strip(), elapsed


def bench_fixtures():
    print("=== Tesseract (chi_tra) on synthetic fixtures ===")
    total = 0.0
    for filename, expected_substring in FIXTURE_EXPECTED.items():
        image_path = FIXTURES_DIR / filename
        text, elapsed = ocr_image(image_path)
        total += elapsed
        match = expected_substring in text
        print(f"{filename}: {elapsed*1000:.0f}ms  text={text!r}  expected_substring_found={match}")
    print(f"total: {total*1000:.0f}ms for {len(FIXTURE_EXPECTED)} images "
          f"({total/len(FIXTURE_EXPECTED)*1000:.0f}ms/image avg)\n")


def bench_real_frames():
    video_path = CACHE_DIR / "video.webm"
    if not video_path.is_file():
        print(f"no cached video at {video_path}, skipping real-frame benchmark")
        return

    print("=== Tesseract (chi_tra) on REAL subtitle frame crops ===")
    out_dir = Path(os.environ.get("TEMP", ".")) / "ytt_tesseract_bench_frames"
    total = 0.0
    for timestamp, expected_substring in REAL_EXPECTED.items():
        frames = extract_frames(
            str(video_path), timestamp, 1, str(out_dir),
            sample_rate_hz=1.0, crop_bottom_fraction=0.25,
        )
        if not frames:
            print(f"t={timestamp}s: no frame extracted, skipping")
            continue

        frame_path, _ = frames[0]
        text, elapsed = ocr_image(frame_path)
        total += elapsed
        match = expected_substring in text
        print(f"t={timestamp}s: {elapsed*1000:.0f}ms  text={text!r}  expected={expected_substring!r}  match={match}")

    print(f"total: {total*1000:.0f}ms for {len(REAL_EXPECTED)} real frames "
          f"({total/len(REAL_EXPECTED)*1000:.0f}ms/frame avg)")


if __name__ == "__main__":
    bench_fixtures()
    bench_real_frames()
