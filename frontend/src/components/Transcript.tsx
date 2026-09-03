import type { TranscriptSegment } from "../types/transcript";

interface TranscriptProps {
  segments: TranscriptSegment[];
  enableOcr: boolean;
}

export default function Transcript({ segments, enableOcr }: TranscriptProps) {
  if (segments.length === 0) {
    return null;
  }

  const transcript = segments.map((s) => s.text).join("\n\n");

  const copyTranscript = async () => {
    await navigator.clipboard.writeText(transcript);
  };

  // Overall live status for the container itself (not just per-segment):
  // grey while anything is still being checked, green once everything
  // resolved is subtitle-confirmed, red if any segment finished as
  // audio-only (unconfirmed against subtitles).
  const containerState = !enableOcr
    ? "neutral"
    : segments.some((s) => s.source === undefined)
      ? "pending"
      : segments.some((s) => s.source === "whisper")
        ? "whisper"
        : "ocr";

  return (
    <div className={`transcript-container transcript-container-${containerState}`}>
      <div className="transcript-header">
        <h2>Transcript</h2>

        <button onClick={copyTranscript}>
          Copy
        </button>
      </div>

      {enableOcr ? (
        <div className="transcript transcript-annotated">
          {segments.map((segment, index) => {
            const state =
              segment.source === "ocr" ? "ocr" : segment.source === "whisper" ? "whisper" : "pending";

            return (
              <p key={index} className={`transcript-segment source-${state}`}>
                <span className="source-badge">
                  {state === "ocr" ? "subtitle" : state === "whisper" ? "audio only" : "checking…"}
                </span>
                {segment.text}
              </p>
            );
          })}
        </div>
      ) : (
        <div className="transcript">
          {transcript}
        </div>
      )}
    </div>
  );
}
