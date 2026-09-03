from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_transcribe_ocr_disabled():
    with client.stream(
        "POST",
        "/transcribe",
        params={
            "url": "https://www.youtube.com/watch?v=_q5BX9nC_M8",
            "enable_ocr": "false",
        },
    ) as response:
        assert response.status_code == 200

        for line in response.iter_lines():
            print("RECEIVED:", line)


if __name__ == "__main__":
    test_transcribe_ocr_disabled()
