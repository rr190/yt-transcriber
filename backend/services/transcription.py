import os
import subprocess
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Groq's free tier caps request audio size — keep chunks comfortably
# under that limit. At 64kbps mp3, 600s (10 min) is ~4.8MB.
CHUNK_SECONDS = 600

# A full 10-minute chunk can take a couple minutes to extract+transcribe
# on a CPU-constrained host, which means the UI shows nothing at all
# until that first chunk finishes. Making just the first chunk short
# gets real transcript text on screen much sooner; every chunk after it
# is full-length as normal.
FIRST_CHUNK_SECONDS = 90

MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3")


def _extract_chunk(file_path: str, start_time: int, duration: int, out_path: str):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-t", str(duration),
            "-i", str(file_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-b:a", "64k",
            out_path,
        ],
        check=True,
        capture_output=True,
    )


def transcribe_segment(
    file_path: str,
    start_time: int,
    segment_duration: int = CHUNK_SECONDS,
    language: str | None = "zh",
):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    chunk_path = f"{file_path}.{start_time}.chunk.mp3"
    label = f"chunk[{start_time}-{start_time + segment_duration}]"

    try:
        print(f"[transcribe {label}] extracting via ffmpeg...", flush=True)
        t0 = time.monotonic()
        _extract_chunk(file_path, start_time, segment_duration, chunk_path)
        extract_elapsed = time.monotonic() - t0
        chunk_size = os.path.getsize(chunk_path) / 1_048_576
        print(
            f"[transcribe {label}] ffmpeg extracted {chunk_size:.1f}MiB in {extract_elapsed:.1f}s, calling Groq...",
            flush=True,
        )

        with open(chunk_path, "rb") as audio_file:
            kwargs = {}
            if language and language != "auto":
                kwargs["language"] = language

            t1 = time.monotonic()
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(chunk_path), audio_file.read()),
                model=MODEL,
                response_format="json",
                **kwargs,
            )
            groq_elapsed = time.monotonic() - t1

        text = transcription.text.strip()
        print(f"[transcribe {label}] Groq responded in {groq_elapsed:.1f}s", flush=True)

        return {
            "start": start_time,
            "end": start_time + segment_duration,
            "text": text,
        }

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg error: {e}")
    except Exception as e:
        raise RuntimeError(f"Transcription error: {e}")
    finally:
        if os.path.exists(chunk_path):
            os.remove(chunk_path)


def _build_segments(duration) -> list[tuple[int, int]]:
    """
    Splits the full duration into (start, length) chunks. The first
    chunk is short (FIRST_CHUNK_SECONDS) so the UI gets real text to
    show quickly; every chunk after that is a normal full-length one.
    """

    duration = int(duration)

    if duration <= 0:
        return [(0, 1)]

    segments: list[tuple[int, int]] = []

    first_len = min(FIRST_CHUNK_SECONDS, duration)
    segments.append((0, first_len))

    start = first_len
    while start < duration:
        length = min(CHUNK_SECONDS, duration - start)
        segments.append((start, length))
        start += length

    return segments


def transcribe_concurrently(
    file_path,
    duration,
    cancel_event,
    language: str | None = "zh",
    max_workers: int = 3,
):
    """
    Yields two kinds of events, both dicts:
      - {"event": "started", "start": ..., "end": ...} — a chunk just
        began extraction/transcription, so the caller can show live
        progress instead of going silent for however long that chunk
        takes.
      - {"event": "done", "start": ..., "end": ..., "text": ...} — a
        chunk finished, yielded strictly in chronological order even
        though workers may complete out of order.
    """

    segments = _build_segments(duration)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict = {}

        def submit(index: int) -> tuple[int, int]:
            start, length = segments[index]

            future = executor.submit(
                transcribe_segment, str(file_path), start, length, language
            )

            futures[future] = (start, length)

            return start, length

        for i in range(min(max_workers, len(segments))):
            if cancel_event.is_set():
                return

            start, length = submit(i)

            yield {"event": "started", "start": start, "end": start + length}

        next_index = max_workers
        pending_results = {}
        yield_pointer = 0

        while futures:
            if cancel_event.is_set():
                print("Cancellation requested.", flush=True)
                return

            done = next(as_completed(futures))
            start, length = futures.pop(done)

            try:
                result = done.result()
                pending_results[start] = result
            except Exception as e:
                print(f"ERROR in segment {start}: {e}", flush=True)
                # Still record a placeholder so ordered yielding isn't
                # blocked forever by one failed chunk.
                pending_results[start] = {
                    "start": start,
                    "end": start + length,
                    "text": "",
                }

            # Yield results in chronological order, even though workers
            # may finish out of order.
            while yield_pointer < len(segments) and segments[yield_pointer][0] in pending_results:
                seg_start = segments[yield_pointer][0]
                result = pending_results.pop(seg_start)
                yield {"event": "done", **result}
                yield_pointer += 1

            if not cancel_event.is_set() and next_index < len(segments):
                start, length = submit(next_index)
                yield {"event": "started", "start": start, "end": start + length}
                next_index += 1
