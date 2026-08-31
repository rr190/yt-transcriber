# YouTube Transcriber

Paste a YouTube link, get a transcript — tuned for Chinese audio. Transcription
runs on [Groq's](https://groq.com) hosted Whisper API (`whisper-large-v3`),
so the backend stays lightweight and free to host.

## How it works

```
React frontend  →  FastAPI backend  →  yt-dlp (audio)  →  Groq Whisper API  →  transcript
```

## Run it locally

**Backend**

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # then add your GROQ_API_KEY (free: console.groq.com/keys)
cd ..
python -m uvicorn backend.main:app --reload --port 8001
```

Requires `ffmpeg`/`ffprobe` on your `PATH`.

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL=http://localhost:8001
npm run dev
```

Open the printed `localhost` URL, paste a YouTube link, pick a language, hit
Transcribe.

## Deploying so you can send someone a link

Everything below is free.

### 1. Get a Groq API key

console.groq.com/keys — no credit card needed.

### 2. Push this repo to GitHub

```bash
git init
git add .
git commit -m "YouTube transcriber"
gh repo create yt-transcriber --public --source=. --push
```

### 3. Deploy the backend on Render

1. [render.com](https://render.com) → New → Web Service → connect your repo.
2. Runtime: **Docker** (it will use the `Dockerfile` at the repo root).
3. Instance type: Free.
4. Environment variables:
   - `GROQ_API_KEY` = your key
   - `FRONTEND_URL` = leave blank for now, fill in after step 4
5. Deploy. Copy the resulting URL, e.g. `https://yt-transcriber.onrender.com`.

Note: Render's free tier spins down after inactivity, so the first request
after a while takes ~30-60s to wake up.

### 4. Deploy the frontend on Vercel

1. [vercel.com](https://vercel.com) → New Project → import your repo.
2. Root directory: `frontend`.
3. Environment variable: `VITE_API_URL` = your Render backend URL from step 3.
4. Deploy. You'll get a URL like `https://yt-transcriber.vercel.app` — this
   is the link you can send to anyone.

### 5. Close the loop on CORS

Go back to Render → your backend's environment variables → set `FRONTEND_URL`
to your Vercel URL → redeploy the backend.

## Known limitations

- **YouTube may occasionally block cloud IPs** with a "sign in to confirm
  you're not a bot" error — this is a YouTube-side anti-bot measure that can
  affect any server-hosted downloader, not something specific to this app.
  It's usually intermittent.
- Very long videos (multiple hours) take longer since audio is chunked into
  10-minute pieces and transcribed a few at a time.
- Render's free tier sleeps when idle — the first request after idle time is
  slow to wake up.
