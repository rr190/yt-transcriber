import type { TranscriptionEvent } from "../types/transcription";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001";

export async function streamTranscription(
  url: string,
  language: string,
  onEvent: (event: TranscriptionEvent) => void,
  signal?: AbortSignal
) {
  const params = new URLSearchParams({ url, language });

  const response = await fetch(`${API_URL}/transcribe?${params.toString()}`, {
    method: "POST",
    signal,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Response does not support streaming");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, {
      stream: true,
    });

    const lines = buffer.split("\n");

    // Keep incomplete line
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) {
        continue;
      }

      const event = JSON.parse(line) as TranscriptionEvent;

      onEvent(event);
    }
  }
}
