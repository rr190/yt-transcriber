"""
Standalone validation of the EasyOCR ch_tra wrapper against known-text
fixture images (backend/tests/fixtures/), independent of the full
download+ffmpeg+scan pipeline. Run this first when touching backend/services/ocr.py
- it's the highest-risk, least-familiar piece of the subtitle-scan feature.

    python -m backend.tests.test_ocr
"""

from pathlib import Path

from backend.services.cleaner import clean_ocr_text
from backend.services.ocr import ocr_frame

FIXTURES_DIR = Path(__file__).parent / "fixtures"

EXPECTED = {
    "greeting.jpg": "你好",       # partial match is fine, OCR line-breaks can vary
    "question.jpg": "這是什麼意思",
    "mixed.jpg": "再見",
}


def test_ocr_fixtures():
    for filename, expected_substring in EXPECTED.items():
        image_path = FIXTURES_DIR / filename
        assert image_path.is_file(), f"missing fixture {image_path} - run make_fixtures.py first"

        detections = ocr_frame(str(image_path))
        text = clean_ocr_text(detections)

        print(f"{filename}: detections={detections}")
        print(f"{filename}: cleaned text={text!r}")

        assert expected_substring in text, (
            f"expected {expected_substring!r} to appear in OCR output {text!r} for {filename}"
        )


if __name__ == "__main__":
    test_ocr_fixtures()
    print("All OCR fixture checks passed.")
