"""Checks whether concurrent calls to a shared EasyOCR Reader are safe
(same results as sequential) before widening OCR concurrency."""
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.services.ocr import ocr_frame
from backend.services.cleaner import clean_ocr_text

FIXTURES_DIR = Path(__file__).parent / "fixtures"
IMAGES = [FIXTURES_DIR / f for f in ["greeting.jpg", "question.jpg", "mixed.jpg"]] * 3  # 9 calls


def run_sequential():
    t0 = time.monotonic()
    results = [clean_ocr_text(ocr_frame(str(p))) for p in IMAGES]
    return results, time.monotonic() - t0


def run_concurrent(workers):
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda p: clean_ocr_text(ocr_frame(str(p))), IMAGES))
    return results, time.monotonic() - t0


if __name__ == "__main__":
    seq_results, seq_time = run_sequential()
    print(f"sequential: {seq_time:.2f}s -> {seq_results}")

    for workers in (2, 4):
        conc_results, conc_time = run_concurrent(workers)
        match = conc_results == seq_results
        print(f"concurrent(workers={workers}): {conc_time:.2f}s -> match_sequential={match}")
        if not match:
            print(f"  MISMATCH: {conc_results}")
