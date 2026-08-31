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

from backend.services.transcription import transcribe_concurrently
from backend.services.youtube import download_audio, get_audio_duration

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
):
    cancel_event = Event()

    # A sentinel to detect generator exhaustion through asyncio.to_thread,
    # which can't distinguish "no more items" from a real yielded value.
    _DONE = object()

    async def generate():
        audio_path = None
        request_start = time.monotonic()

        def log(message: str) -> None:
            print(f"[transcribe +{time.monotonic() - request_start:.1f}s] {message}", flush=True)

        try:
            log(f"request received for {url!r} (language={language!r})")

            # download_audio/get_audio_duration/transcribe_concurrently are
            # all blocking (subprocess calls to yt-dlp/ffmpeg, network
            # calls to Groq). Running them directly on the event loop would
            # freeze the whole server for the duration of every request —
            # with a single worker process, that means no other request
            # (including Render's own health check) gets served, which can
            # get the instance killed/restarted mid-transcription. Pushing
            # each blocking call to a worker thread keeps the loop free.
            log("downloading audio via yt-dlp (this is usually the slow part — see [yt-dlp] logs below)")
            audio_path = await asyncio.to_thread(download_audio, url)
            log(f"audio downloaded to {audio_path}")

            yield json.dumps({"status": "downloaded"}) + "\n"

            duration = await asyncio.to_thread(get_audio_duration, audio_path)
            log(f"audio duration: {duration:.1f}s")

            yield json.dumps({"status": "duration", "duration": duration}) + "\n"

            log("starting transcription")
            segments = transcribe_concurrently(
                audio_path, duration, cancel_event, language=language
            )

            while True:
                raw_result = await asyncio.to_thread(next, segments, _DONE)

                if raw_result is _DONE:
                    break

                result = cast(dict[str, Any], raw_result)

                # Browser disconnected
                if await request.is_disconnected():
                    cancel_event.set()
                    break

                yield json.dumps(
                    {
                        "status": "chunk",
                        "start": result["start"],
                        "end": result["end"],
                        "text": result["text"],
                    },
                    ensure_ascii=False,
                ) + "\n"

            log("transcription complete")
            yield json.dumps({"status": "complete"}) + "\n"

        except Exception as e:
            log(f"error: {e}")
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

        finally:
            cancel_event.set()

            # Clean up the temp directory created for this request.
            if audio_path is not None:
                shutil.rmtree(audio_path.parent, ignore_errors=True)

    return StreamingResponse(generate(), media_type="application/x-ndjson")
