"""Checks whether concurrent calls to a shared RapidOCR engine are safe
(same results as sequential) and measures the concurrency speedup."""
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

FIXTURES_DIR = Path(__file__).parent / "fixtures"
IMAGES = [FIXTURES_DIR / f for f in ["greeting.jpg", "question.jpg", "mixed.jpg"]] * 4  # 12 calls

engine = RapidOCR()


def run_one(path):
    result, _ = engine(str(path))
    return "".join(line[1] for line in result) if result else ""


def run_sequential():
    t0 = time.monotonic()
    results = [run_one(p) for p in IMAGES]
    return results, time.monotonic() - t0


def run_concurrent(workers):
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run_one, IMAGES))
    return results, time.monotonic() - t0


if __name__ == "__main__":
    run_one(IMAGES[0])  # warm-up

    seq_results, seq_time = run_sequential()
    print(f"sequential: {seq_time:.2f}s")

    for workers in (2, 3, 4):
        conc_results, conc_time = run_concurrent(workers)
        match = conc_results == seq_results
        print(f"concurrent(workers={workers}): {conc_time:.2f}s -> match_sequential={match}")
        if not match:
            print(f"  MISMATCH: {conc_results}")
