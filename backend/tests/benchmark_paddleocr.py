"""
Benchmarks PaddleOCR's chinese_cht (Traditional-Chinese-specific) model
against known text, on both synthetic fixtures and a real cropped subtitle
frame pulled from the cached real video clip - same images used for the
RapidOCR and Tesseract benchmarks, for a fair three-way comparison.

    .venv_bench/Scripts/python -m backend.tests.benchmark_paddleocr
"""

import os
import time
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REAL_FRAME = Path(os.environ.get("TEMP", ".")) / "ytt_tesseract_bench_frames" / "frame_000001.jpg"

FIXTURE_EXPECTED = {
    "greeting.jpg": "你好",
    "question.jpg": "這是什麼意思",
    "mixed.jpg": "再見",
}

# Ground truth for the real frame (verified earlier this session).
REAL_EXPECTED = "今天為了寄託定弘"


def main():
    from paddleocr import PaddleOCR

    print("loading PaddleOCR (chinese_cht, this can take a while on first run - downloads model weights)...")
    t0 = time.monotonic()
    ocr = PaddleOCR(lang="chinese_cht", use_textline_orientation=False, use_doc_orientation_classify=False, use_doc_unwarping=False)
    print(f"load time: {time.monotonic()-t0:.1f}s\n")

    def run(image_path):
        result = ocr.predict(str(image_path))
        page = result[0] if result else None
        texts = page["rec_texts"] if page else []
        return "".join(texts)

    # Warm-up
    run(FIXTURES_DIR / "greeting.jpg")

    print("=== PaddleOCR (chinese_cht) on synthetic fixtures ===")
    total = 0.0
    for filename, expected_substring in FIXTURE_EXPECTED.items():
        image_path = FIXTURES_DIR / filename
        t0 = time.monotonic()
        text = run(image_path)
        elapsed = time.monotonic() - t0
        total += elapsed

        match = expected_substring in text
        print(f"{filename}: {elapsed*1000:.0f}ms  text={text!r}  match={match}")
    print(f"total: {total*1000:.0f}ms for {len(FIXTURE_EXPECTED)} images "
          f"({total/len(FIXTURE_EXPECTED)*1000:.0f}ms/image avg)\n")

    if REAL_FRAME.is_file():
        print("=== PaddleOCR (chinese_cht) on a REAL subtitle frame ===")
        t0 = time.monotonic()
        text = run(REAL_FRAME)
        elapsed = time.monotonic() - t0
        match = REAL_EXPECTED in text
        print(f"{elapsed*1000:.0f}ms  text={text!r}  expected={REAL_EXPECTED!r}  match={match}")
    else:
        print(f"no real frame at {REAL_FRAME}, skipping real-frame test")


if __name__ == "__main__":
    main()
