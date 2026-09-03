from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_transcribe_with_ocr():
    with client.stream(
        "POST",
        "/transcribe",
        params={
            # A short, stable video (yt-dlp's own test fixture, ~10s) —
            # used here purely to smoke-test the full pipeline's mechanics
            # (video download, frame extraction, OCR generator, merge,
            # event stream) quickly. OCR accuracy on real Traditional
            # Chinese text is already validated separately by test_ocr.py
            # against known-text fixtures.
            "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "enable_ocr": "true",
        },
    ) as response:
        assert response.status_code == 200

        for line in response.iter_lines():
            print("RECEIVED:", line)


if __name__ == "__main__":
    test_transcribe_with_ocr()
