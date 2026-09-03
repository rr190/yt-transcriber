"""
Generates synthetic burned-in-subtitle fixture images (dark video frame,
white outlined Traditional Chinese subtitle text near the bottom) for
validating the EasyOCR ch_tra pipeline without needing a real video
download. Run once to (re)populate this directory:

    python -m backend.tests.fixtures.make_fixtures
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = r"C:\Windows\Fonts\msjh.ttc"  # Microsoft JhengHei (Traditional Chinese)

FIXTURES = {
    "greeting.jpg": "你好，歡迎收看",
    "question.jpg": "這是什麼意思？",
    "mixed.jpg": "第 3 集 - 再見",
}


def make_frame(text: str, out_path: Path, size=(640, 360)):
    image = Image.new("RGB", size, color=(20, 20, 25))
    draw = ImageDraw.Draw(image)

    font = ImageFont.truetype(FONT_PATH, 32)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (size[0] - text_w) / 2
    y = size[1] - 70

    # White text with a black outline, mimicking typical burned-in
    # subtitle styling.
    for dx in (-2, -1, 0, 1, 2):
        for dy in (-2, -1, 0, 1, 2):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))

    image.save(out_path, quality=90)


if __name__ == "__main__":
    out_dir = Path(__file__).parent
    for filename, text in FIXTURES.items():
        make_frame(text, out_dir / filename)
        print(f"wrote {filename}: {text!r}")
