import subprocess
from pathlib import Path

# Burned-in subtitle lines typically hold for 1.5-4s. Sampling every 4s
# roughly halves total OCR work vs. every 2s (a real lever on long videos -
# EasyOCR is the only accurate engine we've found and it's slow, see
# backend/tests/ocr_engine_comparison.ipynb), at the cost of sometimes
# missing a very short-lived line or catching it only once instead of
# twice (less benefit from the cross-frame dedup in cleaner.py).
DEFAULT_SAMPLE_RATE_HZ = 0.25

# Subtitles usually sit in a consistent band near the bottom of the frame.
# Cropping to this band before OCR both cuts compute (smaller image per
# frame) and cuts false positives from unrelated on-screen text/watermarks.
DEFAULT_CROP_BOTTOM_FRACTION = 0.25

# ffmpeg is invoked once per window (not once per frame) to avoid spawning
# a subprocess per sampled frame. Windows are sized independently of
# Whisper's 600s CHUNK_SECONDS so subtitle-scan progress can stream more
# granularly than the audio transcription does.
FRAME_BATCH_SECONDS = 30


def extract_frames(
    video_path: str,
    start_time: int,
    duration: int,
    out_dir: str,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    crop_bottom_fraction: float = DEFAULT_CROP_BOTTOM_FRACTION,
) -> list[tuple[Path, float]]:
    """
    Extracts cropped, downsampled frames from [start_time, start_time +
    duration) of video_path into out_dir, via a single batched ffmpeg call.

    Returns a list of (frame_path, timestamp_seconds) pairs in chronological
    order. Timestamps are computed from the sample rate rather than trusted
    from ffmpeg's %06d output numbering, so an off-by-one in frame counting
    can't silently corrupt downstream OCR timestamps.
    """

    out_dir_path = Path(out_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)

    crop_filter = (
        f"crop=iw:ih*{crop_bottom_fraction}:0:ih*{1 - crop_bottom_fraction},"
        f"fps={sample_rate_hz}"
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-t", str(duration),
            "-i", str(video_path),
            "-vf", crop_filter,
            "-q:v", "4",
            str(out_dir_path / "frame_%06d.jpg"),
        ],
        check=True,
        capture_output=True,
    )

    frame_paths = sorted(out_dir_path.glob("frame_*.jpg"))

    frame_interval = 1.0 / sample_rate_hz
    results: list[tuple[Path, float]] = []
    for index, frame_path in enumerate(frame_paths):
        timestamp = start_time + index * frame_interval
        results.append((frame_path, timestamp))

    return results
