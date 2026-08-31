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
    path to the resulting mp3 file.

    Encoded at a modest bitrate to keep file size small — this matters
    because the transcription API has a per-request file size limit.
    """

    work_dir = Path(tempfile.mkdtemp(prefix="ytt_"))
    output_template = work_dir / "audio.%(ext)s"

    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "-f",
        "bestaudio",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "64K",
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

            # The raw video download finishing doesn't mean we're done —
            # yt-dlp still has to shell out to ffmpeg to strip/transcode
            # the audio track, which can itself take a while on longer
            # videos. Flag that transition so a stall there doesn't look
            # like a stall in the download itself.
            if "[ExtractAudio] Destination:" in line:
                print(
                    f"[youtube] video downloaded, extracting audio via ffmpeg "
                    f"({time.monotonic() - start:.1f}s elapsed so far)",
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

    audio_path = work_dir / "audio.mp3"

    if not audio_path.exists():
        raise ValueError("Download succeeded but no audio file was produced.")

    return audio_path
