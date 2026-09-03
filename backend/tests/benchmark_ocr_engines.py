"""
Benchmarks RapidOCR (ONNX, PP-OCRv4) against EasyOCR (ch_tra) on our
Traditional Chinese fixtures, for both speed and accuracy. Run with the
benchmark venv (has rapidocr but not necessarily the same easyocr as the
main .venv - install easyocr there too if comparing both in one run, or
run each half separately and compare printed results).

    .venv_bench/Scripts/python -m backend.tests.benchmark_ocr_engines
"""

import time
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"

EXPECTED = {
    "greeting.jpg": "你好",
    "question.jpg": "這是什麼意思",
    "mixed.jpg": "再見",
}


def bench_rapidocr():
    from rapidocr_onnxruntime import RapidOCR

    print("=== RapidOCR (PP-OCRv4, ch) ===")
    engine = RapidOCR()

    # Warm-up (excludes one-time model load from the per-image timing)
    engine(str(FIXTURES_DIR / "greeting.jpg"))

    total_time = 0.0
    for filename, expected_substring in EXPECTED.items():
        image_path = FIXTURES_DIR / filename
        t0 = time.monotonic()
        result, _ = engine(str(image_path))
        elapsed = time.monotonic() - t0
        total_time += elapsed

        text = "".join(line[1] for line in result) if result else ""
        match = expected_substring in text
        print(f"{filename}: {elapsed*1000:.0f}ms  text={text!r}  expected_substring_found={match}")

    print(f"total (excl. warm-up): {total_time*1000:.0f}ms for {len(EXPECTED)} images "
          f"({total_time/len(EXPECTED)*1000:.0f}ms/image avg)")


def bench_easyocr():
    import easyocr

    print("=== EasyOCR (ch_tra + en) ===")
    t0 = time.monotonic()
    reader = easyocr.Reader(["ch_tra", "en"], gpu=False)
    print(f"reader load: {(time.monotonic()-t0)*1000:.0f}ms")

    # Warm-up
    reader.readtext(str(FIXTURES_DIR / "greeting.jpg"))

    total_time = 0.0
    for filename, expected_substring in EXPECTED.items():
        image_path = FIXTURES_DIR / filename
        t0 = time.monotonic()
        detections = reader.readtext(str(image_path))
        elapsed = time.monotonic() - t0
        total_time += elapsed

        text = " ".join(d[1] for d in detections)
        match = expected_substring in text
        print(f"{filename}: {elapsed*1000:.0f}ms  text={text!r}  expected_substring_found={match}")

    print(f"total (excl. warm-up): {total_time*1000:.0f}ms for {len(EXPECTED)} images "
          f"({total_time/len(EXPECTED)*1000:.0f}ms/image avg)")


if __name__ == "__main__":
    import sys

    which = sys.argv[1] if len(sys.argv) > 1 else "both"

    if which in ("rapidocr", "both"):
        try:
            bench_rapidocr()
        except ImportError:
            print("rapidocr_onnxruntime not installed in this environment, skipping")

    if which in ("easyocr", "both"):
        try:
            bench_easyocr()
        except ImportError:
            print("easyocr not installed in this environment, skipping")
