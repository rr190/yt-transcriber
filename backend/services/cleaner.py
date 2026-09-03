MIN_CONFIDENCE = 0.4


def clean_ocr_text(detections: list[dict], min_confidence: float = MIN_CONFIDENCE) -> str:
    """
    Filters low-confidence OCR detections (compression artifacts,
    watermarks, stray noise) and joins what's left into a single line of
    text for one frame.
    """

    kept = [
        d["text"].strip()
        for d in detections
        if d["confidence"] >= min_confidence and d["text"].strip()
    ]
    return " ".join(kept)


def dedupe_lines(texts: list[str]) -> str:
    """
    Collapses consecutive duplicate lines across frames in a window (the
    same subtitle line held across several sampled frames) into a single
    occurrence, preserving order.
    """

    lines: list[str] = []
    for text in texts:
        if not lines or lines[-1] != text:
            lines.append(text)

    return " ".join(lines)
