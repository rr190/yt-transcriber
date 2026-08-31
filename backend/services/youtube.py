import os
import subprocess
import sys
import tempfile
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
    cookies_file = os.environ.get("COOKIES_FILE")
    if cookies_file and Path(cookies_file).is_file():
        command += ["--cookies", cookies_file]

    command.append(url)

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise ValueError(
            "Failed to download audio from the provided URL. "
            f"{e.stderr[-500:] if e.stderr else ''}"
        )
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred: {e}")

    audio_path = work_dir / "audio.mp3"

    if not audio_path.exists():
        raise ValueError("Download succeeded but no audio file was produced.")

    return audio_path
