"""
Validates the OCR-wins merge path against a real video with (assumed)
burned-in Traditional Chinese subtitles, restricted to a short time window
so we don't have to download/scan the whole (very long) source video.

Downloads only [START, END) of the video via yt-dlp's --download-sections
(both audio and video-only streams), then runs the same frame-extraction +
OCR + Whisper + merge pipeline main.py uses, directly - independent of the
/transcribe endpoint, which doesn't support a start/end range.

    python -m backend.tests.run_real_subtitle_check
"""

import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.services.merge import merge_segments
from backend.services.ocr import scan_subtitles_concurrently
from backend.services.transcription import transcribe_segment
from backend.services.youtube import get_audio_duration

URL = "https://www.youtube.com/watch?v=_q5BX9nC_M8"
START = 60
END = 120
SECTION = f"*{START}-{END}"


def download_section(url: str, fmt: str, out_name: str, work_dir: Path) -> Path:
    output_template = work_dir / f"{out_name}.%(ext)s"
    command = [
        sys.executable, "-m", "yt_dlp",
        "-f", fmt,
        "--download-sections", SECTION,
        "-o", str(output_template),
        url,
    ]
    print(f"[download_section] running: {' '.join(command)}", flush=True)
    subprocess.run(command, check=True)

    produced = [p for p in work_dir.glob(f"{out_name}.*")]
    if not produced:
        raise RuntimeError(f"No {out_name} file produced")
    return produced[0]


def main():
    work_dir = Path(tempfile.mkdtemp(prefix="ytt_realcheck_"))
    print(f"[run_real_subtitle_check] work dir: {work_dir}")

    def cached_or_download(fmt: str, out_name: str) -> Path:
        cache_dir = Path(tempfile.gettempdir()) / "ytt_realcheck_cache"
        cache_dir.mkdir(exist_ok=True)
        cached = list(cache_dir.glob(f"{out_name}.*"))
        if cached:
            print(f"[run_real_subtitle_check] reusing cached {cached[0]}")
            return cached[0]
        p = download_section(URL, fmt, out_name, cache_dir)
        return p

    try:
        audio_path = cached_or_download("bestaudio", "audio")
        video_path = cached_or_download("bestvideo[height<=480]/best[height<=480]", "video")

        duration = get_audio_duration(audio_path)
        print(f"[run_real_subtitle_check] clip duration: {duration:.1f}s")

        cancel_event = threading.Event()

        print("[run_real_subtitle_check] transcribing (Whisper)...")
        whisper_result = transcribe_segment(str(audio_path), 0, int(duration), language="zh")
        whisper_segments = [whisper_result]
        print(f"[run_real_subtitle_check] whisper text: {whisper_result['text']!r}")

        print("[run_real_subtitle_check] scanning frames (OCR)...")
        frames_dir = work_dir / "frames"
        ocr_windows = []
        for event in scan_subtitles_concurrently(str(video_path), duration, cancel_event, str(frames_dir)):
            if event["type"] == "frame":
                print(f"  [frame t={event['timestamp']:.1f}s] text={event['text']!r}")
            else:
                print(f"  [window {event['start']}-{event['end']}] text={event['text']!r}")
                ocr_windows.append(event)

        merged = merge_segments(whisper_segments, ocr_windows)
        print("\n[run_real_subtitle_check] MERGED RESULT:")
        for segment in merged:
            print(f"  [{segment['start']}-{segment['end']}] source={segment['source']!r} text={segment['text']!r}")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
