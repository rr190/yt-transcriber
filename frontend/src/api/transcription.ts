import type { TranscriptionEvent } from "../types/transcription";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8001").replace(/\/+$/, "");

export async function streamTranscription(
  url: string,
  language: string,
  onEvent: (event: TranscriptionEvent) => void,
  signal?: AbortSignal,
  enableOcr: boolean = true
) {
  const params = new URLSearchParams({
    url,
    language,
    enable_ocr: String(enableOcr),
  });

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

      // A single network read can contain several NDJSON lines already
      // buffered together (common on a fast/warm backend) - without this,
      // React 18 batches every onEvent() call in this loop into one paint,
      // so a segment's pending -> resolved transition (or a live frame
      // update) could be applied and immediately overwritten before the
      // browser ever draws the intermediate state. Yielding a macrotask
      // between events guarantees each one gets its own paint, so the
      // live progress is actually visible rather than just logically
      // "correct but instantaneous."
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  }
}
