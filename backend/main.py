import asyncio
import json
import os
import shutil
import time
from pathlib import Path
from threading import Event
from typing import Any, cast

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.services.merge import merge_segments
from backend.services.ocr import scan_subtitles_concurrently
from backend.services.transcription import transcribe_concurrently
from backend.services.youtube import (
    download_audio,
    download_video_lowres,
    get_audio_duration,
)

app = FastAPI()

default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
]

# In production, set FRONTEND_URL to your deployed Vercel URL.
frontend_url = os.environ.get("FRONTEND_URL")
allow_origins = default_origins + ([frontend_url] if frontend_url else [])

# Vercel gives every preview deployment its own random-hash subdomain
# (e.g. yt-transcriber-eqprw5ez1-jr-61b3.vercel.app), so a single exact
# FRONTEND_URL only ever covers production. This regex additionally
# allows any preview/production URL under the same Vercel project name.
vercel_project = os.environ.get("VERCEL_PROJECT_NAME", "yt-transcriber")
allow_origin_regex = rf"^https://{vercel_project}(-[a-zA-Z0-9]+)*\.vercel\.app$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "YouTube Transcriber API is running."}


@app.post("/transcribe")
async def transcribe_audio_endpoint(
    url: str,
    request: Request,
    language: str = "zh",
    enable_ocr: bool = True,
):
    cancel_event = Event()

    # A sentinel to detect generator exhaustion through asyncio.to_thread,
    # which can't distinguish "no more items" from a real yielded value.
    _DONE = object()

    async def _drain(gen, queue: asyncio.Queue, tag: str):
        """
        Runs a blocking generator to completion in a worker thread,
        forwarding each item onto a shared asyncio.Queue so the async
        generate() below can interleave events from multiple blocking
        generators (Whisper + OCR) as they actually arrive, instead of
        having to fully finish one before starting the other.
        """

        try:
            while True:
                item = await asyncio.to_thread(next, gen, _DONE)
                if item is _DONE:
                    break
                await queue.put((tag, item))
        except Exception as e:
            await queue.put((tag, e))
        finally:
            await queue.put((tag, _DONE))

    async def generate():
        audio_path = None
        video_path = None
        request_start = time.monotonic()

        def log(message: str) -> None:
            print(f"[transcribe +{time.monotonic() - request_start:.1f}s] {message}", flush=True)

        try:
            log(f"request received for {url!r} (language={language!r}, enable_ocr={enable_ocr})")

            # download_audio/download_video_lowres/get_audio_duration/
            # transcribe_concurrently/scan_subtitles_concurrently are all
            # blocking (subprocess calls to yt-dlp/ffmpeg, network calls to
            # Groq, CPU-bound OCR). Running them directly on the event loop
            # would freeze the whole server for the duration of every
            # request — with a single worker process, that means no other
            # request (including Render's own health check) gets served.
            # Pushing each blocking call to a worker thread keeps the loop
            # free.
            log("downloading audio via yt-dlp (this is usually the slow part — see [yt-dlp] logs below)")

            if enable_ocr:
                audio_path, video_path = await asyncio.gather(
                    asyncio.to_thread(download_audio, url),
                    asyncio.to_thread(download_video_lowres, url),
                )
                log(f"audio downloaded to {audio_path}, video downloaded to {video_path}")
                yield json.dumps({"status": "video_downloaded"}) + "\n"
            else:
                audio_path = await asyncio.to_thread(download_audio, url)
                log(f"audio downloaded to {audio_path}")

            yield json.dumps({"status": "downloaded"}) + "\n"

            duration = await asyncio.to_thread(get_audio_duration, audio_path)
            log(f"audio duration: {duration:.1f}s")

            yield json.dumps({"status": "duration", "duration": duration}) + "\n"

            log("starting transcription" + (" + subtitle scan" if enable_ocr else ""))

            whisper_segments: list[dict] = []
            ocr_windows: list[dict] = []
            merged_starts: set[int] = set()
            ocr_scan_progress = 0.0
            ocr_finished = False

            queue: asyncio.Queue = asyncio.Queue()
            tasks = [
                asyncio.create_task(_drain(
                    transcribe_concurrently(audio_path, duration, cancel_event, language=language),
                    queue,
                    "whisper",
                ))
            ]

            if enable_ocr:
                assert video_path is not None
                frames_dir = video_path.parent / "frames"
                tasks.append(asyncio.create_task(_drain(
                    scan_subtitles_concurrently(str(video_path), duration, cancel_event, str(frames_dir)),
                    queue,
                    "ocr",
                )))

            active = len(tasks)

            while active > 0:
                tag, item = await queue.get()
                disconnected = False

                if item is _DONE:
                    active -= 1
                    if tag == "ocr":
                        ocr_finished = True
                elif isinstance(item, Exception):
                    raise item
                elif await request.is_disconnected():
                    # Browser disconnected
                    cancel_event.set()
                    disconnected = True
                elif tag == "whisper":
                    result = cast(dict[str, Any], item)
                    whisper_segments.append(result)
                    yield json.dumps(
                        {
                            "status": "chunk",
                            "start": result["start"],
                            "end": result["end"],
                            "text": result["text"],
                        },
                        ensure_ascii=False,
                    ) + "\n"
                elif tag == "ocr":
                    event = cast(dict[str, Any], item)
                    if event["type"] == "frame":
                        yield json.dumps(
                            {
                                "status": "scanning_frame",
                                "timestamp": event["timestamp"],
                                "text_found": event["text"],
                                "thumbnail": event["thumbnail"],
                            },
                            ensure_ascii=False,
                        ) + "\n"
                    else:  # "window"
                        ocr_windows.append(event)
                        ocr_scan_progress = max(ocr_scan_progress, event["end"])
                        yield json.dumps(
                            {
                                "status": "ocr_window",
                                "start": event["start"],
                                "end": event["end"],
                                "text": event["text"],
                            },
                            ensure_ascii=False,
                        ) + "\n"

                if disconnected:
                    break

                # Merge and emit each Whisper chunk as soon as OCR's scan
                # progress has passed it (or OCR has finished entirely) -
                # rather than waiting for the whole video, so the frontend
                # can flip each segment from pending to green/red as its
                # answer becomes knowable, in sync with the live frame scan.
                # This must run on EVERY loop iteration, including when the
                # item was a _DONE sentinel (that's how ocr_finished ever
                # gets to trigger a merge for chunks OCR's scan progress
                # alone doesn't cover, e.g. a chunk end that isn't an exact
                # window boundary).
                if enable_ocr:
                    for chunk in whisper_segments:
                        if chunk["start"] in merged_starts:
                            continue
                        if not (ocr_finished or ocr_scan_progress >= chunk["end"]):
                            continue

                        merged_chunk = merge_segments(
                            [chunk],
                            [
                                w for w in ocr_windows
                                if w["start"] < chunk["end"] and w["end"] > chunk["start"]
                            ],
                        )[0]
                        merged_starts.add(chunk["start"])

                        yield json.dumps(
                            {
                                "status": "merged_chunk",
                                "start": merged_chunk["start"],
                                "end": merged_chunk["end"],
                                "text": merged_chunk["text"],
                                "source": merged_chunk["source"],
                            },
                            ensure_ascii=False,
                        ) + "\n"

            for task in tasks:
                task.cancel()

            log("transcription complete")
            yield json.dumps({"status": "complete"}) + "\n"

        except Exception as e:
            log(f"error: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

        finally:
            cancel_event.set()

            # Clean up the temp directories created for this request.
            if audio_path is not None:
                shutil.rmtree(audio_path.parent, ignore_errors=True)
            if video_path is not None:
                shutil.rmtree(video_path.parent, ignore_errors=True)

    return StreamingResponse(generate(), media_type="application/x-ndjson")
