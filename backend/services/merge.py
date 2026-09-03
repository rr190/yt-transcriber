def merge_segments(whisper_segments: list[dict], ocr_windows: list[dict]) -> list[dict]:
    """
    Reconciles Whisper's audio-transcript chunks (600s each, no word-level
    timestamps in the current API call) with OCR's finer subtitle-scan
    windows (FRAME_BATCH_SECONDS each).

    v1 approach: merge at Whisper's own chunk granularity. For each Whisper
    chunk, collect every OCR window that overlaps it; if any of them found
    non-empty subtitle text, concatenate that OCR text (in chronological
    order) and use it as the chunk's output (source="ocr") - subtitles win
    on disagreement per the product decision. If OCR found nothing anywhere
    in that chunk's time range, fall back to the Whisper text unchanged
    (source="whisper").

    A finer per-OCR-window merge would need Whisper's response_format
    switched to "verbose_json" for sub-segment timestamps - a documented
    fast-follow, not done here.
    """

    merged = []

    for chunk in whisper_segments:
        start, end = chunk["start"], chunk["end"]

        overlapping_text = [
            w["text"]
            for w in ocr_windows
            if w["text"] and w["start"] < end and w["end"] > start
        ]

        if overlapping_text:
            merged.append({
                "start": start,
                "end": end,
                "text": " ".join(overlapping_text),
                "source": "ocr",
            })
        else:
            merged.append({
                "start": start,
                "end": end,
                "text": chunk["text"],
                "source": "whisper",
            })

    return merged
