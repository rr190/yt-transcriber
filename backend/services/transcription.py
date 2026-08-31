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


def transcribe_concurrently(
    file_path,
    duration,
    cancel_event,
    language: str | None = "zh",
    max_workers: int = 3,
):
    starts = list(range(0, int(duration), CHUNK_SECONDS))

    if not starts:
        starts = [0]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}

        for start in starts[:max_workers]:
            if cancel_event.is_set():
                return

            remaining = min(CHUNK_SECONDS, max(duration - start, 1))

            future = executor.submit(
                transcribe_segment, str(file_path), start, remaining, language
            )

            futures[future] = start

        next_index = max_workers
        pending_results = {}
        yield_pointer = 0

        while futures:
            if cancel_event.is_set():
                print("Cancellation requested.", flush=True)
                return

            done = next(as_completed(futures))
            start = futures.pop(done)

            try:
                result = done.result()
                pending_results[start] = result
            except Exception as e:
                print(f"ERROR in segment {start}: {e}", flush=True)
                # Still record a placeholder so ordered yielding isn't
                # blocked forever by one failed chunk.
                pending_results[start] = {
                    "start": start,
                    "end": start + CHUNK_SECONDS,
                    "text": "",
                }

            # Yield results in chronological order, even though workers
            # may finish out of order.
            while yield_pointer < len(starts) and starts[yield_pointer] in pending_results:
                yield pending_results.pop(starts[yield_pointer])
                yield_pointer += 1

            if not cancel_event.is_set() and next_index < len(starts):
                next_start = starts[next_index]
                remaining = min(CHUNK_SECONDS, max(duration - next_start, 1))

                future = executor.submit(
                    transcribe_segment,
                    str(file_path),
                    next_start,
                    remaining,
                    language,
                )

                futures[future] = next_start
                next_index += 1
