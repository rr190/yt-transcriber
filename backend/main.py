import json
import os
import shutil
from pathlib import Path
from threading import Event

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
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

    async def generate():
        audio_path = None

        try:
            audio_path = download_audio(url)

            yield json.dumps({"status": "downloaded"}) + "\n"

            duration = get_audio_duration(audio_path)

            yield json.dumps({"status": "duration", "duration": duration}) + "\n"

            for result in transcribe_concurrently(
                audio_path, duration, cancel_event, language=language
            ):
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

            yield json.dumps({"status": "complete"}) + "\n"

        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

        finally:
            cancel_event.set()

            # Clean up the temp directory created for this request.
            if audio_path is not None:
                shutil.rmtree(audio_path.parent, ignore_errors=True)

    return StreamingResponse(generate(), media_type="application/x-ndjson")
