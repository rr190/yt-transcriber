import base64
import queue
import shutil
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.services.cleaner import clean_ocr_text, dedupe_lines
from backend.services.frames import (
    DEFAULT_CROP_BOTTOM_FRACTION,
    DEFAULT_SAMPLE_RATE_HZ,
    FRAME_BATCH_SECONDS,
    extract_frames,
)

# Tried switching to RapidOCR (ONNX, PP-OCRv4 "ch" models) for speed - it
# was genuinely faster (~3-6x on clean synthetic fixtures) and lighter (no
# torch dependency), but on REAL video frames (backend/tests/run_real_subtitle_check.py)
# its generic "ch" model produced noticeably worse Traditional Chinese
# recognition than EasyOCR's ch_tra (real misreadings: 幾->襄, 對->街/野,
# 永遠->水康/水速, a whole line dropped, 壽 dropped from a title) - a real
# accuracy regression, not just a Simplified/Traditional style difference,
# and this feature's whole point is OCR overriding Whisper on disagreement,
# so garbled OCR text would override *correct* Whisper output. Reverted to
# EasyOCR; worth revisiting with a proper Traditional-Chinese-specific
# model (e.g. PaddleOCR's dedicated chinese_cht weights, not RapidOCR's
# bundled generic "ch" ones) rather than EasyOCR's general-purpose speed.
LANGUAGES = ["ch_tra", "en"]

_reader = None
_reader_lock = threading.Lock()


def get_reader():
    """
    Lazily loads a single EasyOCR Reader per process (model loading is
    expensive - seconds of latency and real memory - so this must not
    happen per request). gpu=False is explicit since Render's free tier
    (and most simple deploys) have no GPU; it also avoids EasyOCR probing
    for CUDA at import time.
    """

    global _reader

    if _reader is None:
        with _reader_lock:
            if _reader is None:
                import easyocr

                print("[ocr] loading EasyOCR reader (first use, this can take a while)...", flush=True)
                t0 = time.monotonic()
                _reader = easyocr.Reader(LANGUAGES, gpu=False)
                print(f"[ocr] EasyOCR reader loaded in {time.monotonic() - t0:.1f}s", flush=True)

    return _reader


def ocr_frame(image_path) -> list[dict]:
    """
    Runs EasyOCR on a single cropped frame. Returns raw detections:
    [{"text": str, "confidence": float}, ...]
    """

    reader = get_reader()
    detections = reader.readtext(str(image_path))

    return [
        {"text": text, "confidence": float(confidence)}
        for (_bbox, text, confidence) in detections
    ]


# Validated experimentally (backend/tests/check_ocr_thread_safety.py):
# concurrent calls to a single shared EasyOCR Reader are thread-safe
# (results identical to sequential) and ~3.3x faster with 2 workers, with
# only marginal further gains beyond that - OCR inference saturates CPU
# quickly. Kept modest to avoid oversubscribing alongside Whisper's own
# concurrent chunk transcription running at the same time.
DEFAULT_OCR_WORKERS = 3

_PRODUCER_DONE = object()


def scan_subtitles_concurrently(
    video_path: str,
    duration: float,
    cancel_event: threading.Event,
    frames_dir: str,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    crop_bottom_fraction: float = DEFAULT_CROP_BOTTOM_FRACTION,
    max_workers: int = DEFAULT_OCR_WORKERS,
):
    """
    Generator mirroring transcription.transcribe_concurrently's ordering
    idiom, applied at frame (not window) granularity: a background thread
    extracts frames window-by-window (ffmpeg is fast/batched, so this
    stays well ahead of OCR) and feeds them into a queue; up to
    max_workers frames are OCR'd concurrently, but results are always
    yielded in chronological order via the same pending/yield_pointer
    buffering already used elsewhere in this codebase.

    Two kinds of items are yielded, distinguished by "type":
      {"type": "frame", "timestamp": float, "text": str | None, "thumbnail": str}
        - one per sampled frame, as soon as it's OCR'd (drives the live
          "checking frame at ..." progress UI) - genuinely live, since
          frame-level (not window-level) concurrency means a frame is
          yielded the moment its own OCR call finishes, not once its
          whole window is done.
      {"type": "window", "start": int, "end": int, "text": str}
        - one per FRAME_BATCH_SECONDS window, once all its frames are done
          (the raw, pre-merge OCR text for that window, for merge.py).
    """

    starts = list(range(0, max(int(duration), 1), FRAME_BATCH_SECONDS))
    if not starts:
        starts = [0]

    task_queue: "queue.Queue" = queue.Queue(maxsize=4 * max_workers)

    def producer():
        try:
            for start in starts:
                if cancel_event.is_set():
                    break

                window_duration = min(FRAME_BATCH_SECONDS, max(duration - start, 1))
                window_dir = Path(frames_dir) / f"window_{start}"
                end = start + int(window_duration)

                try:
                    frames = extract_frames(
                        video_path,
                        start,
                        int(window_duration),
                        str(window_dir),
                        sample_rate_hz=sample_rate_hz,
                        crop_bottom_fraction=crop_bottom_fraction,
                    )
                except Exception as e:
                    print(f"[ocr] ERROR extracting window {start}: {e}", flush=True)
                    frames = []

                for frame_path, timestamp in frames:
                    task_queue.put(("frame", frame_path, timestamp))

                task_queue.put(("window_end", start, end, window_dir))
        finally:
            task_queue.put(_PRODUCER_DONE)

    producer_thread = threading.Thread(target=producer, daemon=True)
    producer_thread.start()

    def run_task(task):
        kind = task[0]

        if kind == "frame":
            _, frame_path, timestamp = task
            detections = ocr_frame(frame_path)
            text = clean_ocr_text(detections)

            # Send the actual cropped frame along with each event so the
            # UI can show what the scan is looking at right now, not just
            # a text log - the point is to make the checking visibly
            # real. Frames are already cropped to the subtitle band and
            # jpeg-compressed, so this stays small.
            thumbnail_b64 = base64.b64encode(frame_path.read_bytes()).decode("ascii")

            return {
                "type": "frame",
                "timestamp": timestamp,
                "text": text or None,
                "thumbnail": thumbnail_b64,
            }

        _, start, end, window_dir = task
        return {"type": "_window_end", "start": start, "end": end, "window_dir": window_dir}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        next_seq = 0
        pending_results = {}
        yield_pointer = 0
        producer_finished = False
        current_window_texts: list[str] = []

        def submit_next():
            nonlocal next_seq, producer_finished
            item = task_queue.get()
            if item is _PRODUCER_DONE:
                producer_finished = True
                return
            futures[executor.submit(run_task, item)] = next_seq
            next_seq += 1

        while len(futures) < max_workers and not producer_finished:
            if cancel_event.is_set():
                return
            submit_next()

        while futures:
            if cancel_event.is_set():
                print("[ocr] cancellation requested.", flush=True)
                return

            done = next(as_completed(futures))
            seq = futures.pop(done)

            try:
                result = done.result()
            except Exception as e:
                print(f"[ocr] ERROR in OCR task {seq}: {e}", flush=True)
                result = {"type": "frame", "timestamp": 0.0, "text": None, "thumbnail": ""}

            pending_results[seq] = result

            while yield_pointer in pending_results:
                item = pending_results.pop(yield_pointer)
                yield_pointer += 1

                if item["type"] == "frame":
                    yield item
                    if item["text"]:
                        current_window_texts.append(item["text"])
                else:  # "_window_end"
                    window_text = dedupe_lines(current_window_texts)
                    current_window_texts = []

                    yield {
                        "type": "window",
                        "start": item["start"],
                        "end": item["end"],
                        "text": window_text,
                    }

                    shutil.rmtree(item["window_dir"], ignore_errors=True)

            if not cancel_event.is_set() and not producer_finished:
                submit_next()
