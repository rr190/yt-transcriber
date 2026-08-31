# YouTube Transcript Generator — Development Plan

## 1. Project Goal

Build a web application where a user can:

1. Open a shareable website link.
2. Paste a YouTube video URL.
3. Submit the URL.
4. The backend downloads the video's audio.
5. Whisper transcribes the audio.
6. The transcript is returned to the user.
7. The user can copy or download the transcript.

### Example User Flow

```text
User
  ↓
Paste YouTube URL
  ↓
Click "Transcribe"
  ↓
Backend downloads audio
  ↓
Whisper transcription
  ↓
Clean transcript
  ↓
Display transcript
  ↓
Copy / Download
```

---

## 2. Recommended Tech Stack

### Frontend

* React
* TypeScript
* Tailwind CSS

### Backend

* Python
* FastAPI
* yt-dlp
* Whisper

### Deployment

Initial deployment:

* Frontend: Vercel
* Backend: Render / Railway

Later:

* Custom domain
* Cloud storage
* Background job queue

---

## 3. Project Structure

```text
youtube-transcriber/
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── services/
│   │   ├── youtube.py
│   │   ├── transcription.py
│   │   └── cleaner.py
│   └── temp/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── UrlInput.tsx
│   │   │   ├── Transcript.tsx
│   │   │   └── Loading.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
│
├── .gitignore
├── README.md
└── plan.md
```

---

# 4. Phase 1 — Build the Backend

## Step 1: Create FastAPI application

Create:

```text
backend/main.py
```

Start with:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "YouTube Transcriber API"}
```

Run:

```bash
uvicorn main:app --reload
```

Verify:

```text
http://localhost:8001
```

---

## Step 2: Add YouTube downloading

Install:

```bash
pip install yt-dlp
```

Create:

```text
backend/services/youtube.py
```

The function should:

```python
def download_audio(url: str) -> str:
    ...
```

Responsibilities:

* Validate the YouTube URL.
* Download audio only.
* Save it temporarily.
* Return the audio file path.

Example:

```text
YouTube URL
     ↓
yt-dlp
     ↓
audio.mp3
```

Do not permanently store downloaded videos.

---

# 5. Phase 2 — Add Whisper

Install Whisper and its dependencies.

```bash
pip install openai-whisper
```

Create:

```text
backend/services/transcription.py
```

Implement:

```python
def transcribe(audio_path: str) -> str:
    ...
```

Basic flow:

```python
import whisper

model = whisper.load_model("small")

result = model.transcribe(audio_path)

return result["text"]
```

---

## Model Selection

Start with:

```text
small
```

Possible later options:

```text
tiny    → fastest
base    → faster / reasonable quality
small   → good starting point
medium  → better quality / slower
large   → highest quality / expensive
```

For the first version, prioritize getting the complete pipeline working.

---

# 6. Phase 3 — Create API Endpoint

Add an endpoint such as:

```text
POST /transcribe
```

Request:

```json
{
  "url": "https://www.youtube.com/watch?v=..."
}
```

Response:

```json
{
  "transcript": "This is the transcript..."
}
```

Full flow:

```text
POST /transcribe
       ↓
Validate URL
       ↓
Download audio
       ↓
Whisper
       ↓
Clean transcript
       ↓
Delete temporary audio
       ↓
Return transcript
```

---

# 7. Phase 4 — Add Error Handling

The API should handle:

### Invalid URL

```json
{
  "error": "Invalid YouTube URL"
}
```

### Video unavailable

```json
{
  "error": "Unable to access this video"
}
```

### No audio

```json
{
  "error": "No usable audio was found"
}
```

### Transcription failure

```json
{
  "error": "Transcription failed"
}
```

### Very long videos

Add a maximum duration.

For example:

```text
Maximum video length: 2 hours
```

This prevents someone from sending an extremely large video and consuming all server resources.

---

# 8. Phase 5 — Build Frontend

Create the React application.

The main page should contain:

```text
--------------------------------------

       YouTube Transcript Generator

Paste a YouTube URL

[ https://youtube.com/...             ]

             [ Transcribe ]

--------------------------------------
```

After submission:

```text
Transcribing...

██████████████░░░░░░

This may take a few minutes.
```

Then:

```text
--------------------------------------

Transcript

[ transcript text here                ]
[                                      ]
[                                      ]

[ Copy ]       [ Download ]

--------------------------------------
```

---

# 9. Phase 6 — Connect Frontend to Backend

The frontend sends:

```text
POST /transcribe
```

Example:

```typescript
const response = await fetch(
  "https://your-backend-url.com/transcribe",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      url: youtubeUrl
    })
  }
);

const data = await response.json();
```

Display:

```typescript
data.transcript
```

---

# 10. Phase 7 — Improve Transcript Quality

Raw Whisper output may contain unnecessary spacing and formatting.

Create:

```text
services/cleaner.py
```

Possible cleaning:

* Remove excessive whitespace.
* Fix paragraph breaks.
* Remove duplicate segments.
* Normalize punctuation.
* Preserve timestamps if required.

Eventually add:

```text
Raw Whisper transcript
        ↓
Transcript cleaner
        ↓
Formatted transcript
```

---

# 11. Phase 8 — Add Timestamps

Instead of only returning:

```text
This is the transcript...
```

return segments:

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "text": "Welcome to the video."
    },
    {
      "start": 4.2,
      "end": 8.7,
      "text": "Today we're going to discuss..."
    }
  ]
}
```

Frontend can display:

```text
[00:00] Welcome to the video.

[00:04] Today we're going to discuss...

[00:08] ...
```

This makes the tool significantly more useful.

---

# 12. Phase 9 — Add Copy and Download

### Copy

Add a button that copies the transcript to the clipboard.

### Download

Allow:

```text
Download .txt
Download .srt
```

Later:

```text
Download .pdf
Download .docx
```

---

# 13. Phase 10 — Deploy

## Backend

Push the project to GitHub.

Deploy the backend using:

* Render
* Railway
* Fly.io
* AWS

Set environment/configuration variables as needed.

The backend should expose:

```text
https://your-backend.com
```

---

## Frontend

Deploy the React application using:

* Vercel

The frontend becomes:

```text
https://your-transcriber.vercel.app
```

This is the link you can send to someone.

---

# 14. Phase 11 — CORS

Because the frontend and backend are deployed separately, configure FastAPI CORS.

Example:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-transcriber.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

During development you can temporarily allow:

```text
http://localhost:5173
```

---

# 15. Phase 12 — Production Improvements

Once the basic version works, add:

### Background Jobs

Transcription can take a while, so avoid keeping a normal HTTP request open indefinitely.

Architecture:

```text
User
 ↓
POST /transcribe
 ↓
Create job
 ↓
Return job ID
 ↓
Background worker
 ↓
yt-dlp
 ↓
Whisper
 ↓
Save transcript
 ↓
Frontend checks job status
```

Example:

```text
POST /transcribe

{
    "job_id": "abc123"
}
```

Then:

```text
GET /transcribe/abc123
```

returns:

```json
{
  "status": "processing"
}
```

or:

```json
{
  "status": "complete",
  "transcript": "..."
}
```

---

# 16. Security / Abuse Prevention

Because the app is publicly accessible, users could abuse the transcription endpoint.

Add:

* Rate limiting
* Maximum video duration
* Maximum file size
* Request validation
* Temporary file cleanup
* Timeouts
* IP-based throttling

Do not permanently store downloaded YouTube audio unless there is a clear reason and appropriate rights.

---

# 17. Optional AI Features

Once transcription works, add an LLM layer.

Possible features:

```text
YouTube URL
     ↓
Transcription
     ↓
    ┌───────────────┐
    ↓               ↓
Transcript       AI processing
                    ↓
          ┌─────────┼─────────┐
          ↓         ↓         ↓
       Summary    Notes    Q&A
```

Features:

### Summarise

```text
Generate a concise summary.
```

### Key points

```text
Extract the 5 most important points.
```

### Ask questions

```text
User: What did the speaker say about AI?

LLM → answer based on transcript
```

### Chapters

Automatically generate:

```text
00:00 Introduction
03:24 Background
08:12 Main argument
15:47 Conclusion
```

---

# 18. MVP Checklist

## Backend

* [ ] FastAPI setup
* [ ] YouTube URL validation
* [ ] yt-dlp integration
* [ ] Audio extraction
* [ ] Whisper integration
* [ ] Transcript API
* [ ] Error handling
* [ ] Temporary file cleanup

## Frontend

* [ ] URL input
* [ ] Submit button
* [ ] Loading state
* [ ] Error state
* [ ] Transcript display
* [ ] Copy button
* [ ] Download button

## Deployment

* [ ] GitHub repository
* [ ] Deploy backend
* [ ] Deploy frontend
* [ ] Configure CORS
* [ ] Test public URL

---

# 19. Version 2 Checklist

* [ ] Timestamped transcripts
* [ ] SRT export
* [ ] Background transcription jobs
* [ ] Progress indicator
* [ ] Transcript history
* [ ] AI summaries
* [ ] AI Q&A
* [ ] Automatic chapters
* [ ] Rate limiting
* [ ] Custom domain

---

# 20. Final MVP

The first version should be kept simple:

```text
                    ┌──────────────────┐
                    │   React Website  │
                    │                  │
                    │ Paste YouTube URL│
                    │    [Transcribe]  │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │    FastAPI       │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │     yt-dlp       │
                    │   Extract Audio  │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │     Whisper      │
                    │   Transcription  │
                    └────────┬─────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │    Transcript    │
                    │                  │
                    │ [Copy] [Download]│
                    └──────────────────┘
```

### First milestone

Get this working locally:

```text
YouTube URL
     ↓
Python
     ↓
yt-dlp
     ↓
Whisper
     ↓
transcript.txt
```

Then add FastAPI.

Then add React.

Then deploy.

**Do not start with deployment, databases, authentication, or AI summaries. Get the transcription pipeline working end-to-end first.**
