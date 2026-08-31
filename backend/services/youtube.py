import os
import shutil
import subprocess
import sys
import tempfile
import time
import json
from pathlib import Path


def get_audio_duration(file_path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(file_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)

    return float(data["format"]["duration"])


def download_audio(url: str) -> Path:
    """
    Downloads the audio for a YouTube video into its own temporary
    directory (so concurrent requests never collide) and returns the
    path to the resulting audio file, in whatever container YouTube
    served it in (webm/opus, m4a, ...).

    We deliberately do NOT ask yt-dlp to re-encode this to mp3 (no -x /
    --audio-format): transcription.py's transcribe_segment() already
    re-encodes each ~10min chunk to mp3 64k on its own right before
    sending it to the transcription API. Re-encoding the *whole* file
    here first was pure waste — it's CPU-bound work done twice over the
    entire audio, which on a CPU-constrained host (e.g. Render's free
    tier) was the actual source of the multi-minute "stuck at
    extracting audio" stalls. ffmpeg/ffprobe can read any container
    directly, so skipping this doesn't cost us anything downstream.
    """

    work_dir = Path(tempfile.mkdtemp(prefix="ytt_"))
    output_template = work_dir / "audio.%(ext)s"

    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-f",
        "bestaudio",
        "-o",
        str(output_template),
    ]

    # YouTube frequently challenges requests from cloud/datacenter IPs
    # (Render, AWS, etc.) with "Sign in to confirm you're not a bot".
    # Set COOKIES_FILE (Render: add a secret file + env var pointing at
    # it) to a cookies.txt exported from a logged-in browser session to
    # work around this. Transparent to end users — no upload needed.
    #
    # Render secret files are mounted read-only, but yt-dlp rewrites the
    # cookie jar in place after each run (cookies get rotated during use)
    # — so copy it into our writable per-request work_dir first.
    cookies_file = os.environ.get("COOKIES_FILE")
    if cookies_file and Path(cookies_file).is_file():
        writable_cookies = work_dir / "cookies.txt"
        shutil.copyfile(cookies_file, writable_cookies)
        command += ["--cookies", str(writable_cookies)]

    command.append(url)

    # yt-dlp against YouTube (extractor negotiation, format selection,
    # bot-check challenges, then the actual download/transcode) is the
    # single biggest chunk of the ">40s with zero feedback" complaint.
    # subprocess.run(capture_output=True) buffers everything until the
    # process exits, so nothing is visible while it's stuck. Stream the
    # output line-by-line to our own stdout instead (prefixed + timestamped)
    # so `render logs` / the local console shows what yt-dlp is doing in
    # real time, while still keeping the tail of it for error messages.
    print(f"[youtube] starting yt-dlp for {url}", flush=True)
    start = time.monotonic()
    output_lines: list[str] = []

    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None
        for line in process.stdout:
            line = line.rstrip("\n")
            print(f"[yt-dlp] {line}", flush=True)
            output_lines.append(line)

            # We no longer ask yt-dlp to transcode (see docstring), so
            # this is normally just a straight download. But flag it if
            # yt-dlp ever still invokes a postprocessor (e.g. a remux),
            # so a stall there doesn't look like a stall in the raw
            # download itself.
            if "Destination:" in line and "[download]" not in line:
                print(
                    f"[youtube] post-processing step started "
                    f"({time.monotonic() - start:.1f}s elapsed so far): {line}",
                    flush=True,
                )

        returncode = process.wait()
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred: {e}")

    elapsed = time.monotonic() - start
    print(f"[youtube] yt-dlp exited {returncode} after {elapsed:.1f}s", flush=True)

    if returncode != 0:
        tail = "\n".join(output_lines[-20:])
        raise ValueError(
            f"Failed to download audio from the provided URL. {tail[-500:]}"
        )

    # Extension varies with whatever format YouTube served as "bestaudio"
    # (webm, m4a, opus, ...) since we're no longer forcing a re-encode.
    produced = [
        p for p in work_dir.glob("audio.*") if p.name != "cookies.txt"
    ]

    if not produced:
        raise ValueError("Download succeeded but no audio file was produced.")

    audio_path = produced[0]
    print(f"[youtube] audio file: {audio_path.name} ({audio_path.stat().st_size / 1_048_576:.1f} MiB)", flush=True)

    return audio_path
