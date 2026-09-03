function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0:00";
  }

  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);

  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

interface OcrTraceProps {
  events: { timestamp: number; textFound: string | null }[];
  currentFrame: { timestamp: number; thumbnail: string } | null;
}

// Left: a line-by-line checklist of every frame checked so far (green =
// subtitle text found, red = none found at that timestamp). Right: the
// actual video frame being checked right now. Together this makes the
// scan visibly real — the same line-by-line check the user will do by eye
// against the video once they see the result, done live up front.
export default function OcrTrace({ events, currentFrame }: OcrTraceProps) {
  if (events.length === 0 && !currentFrame) {
    return null;
  }

  // Most recent first, capped so the DOM doesn't grow unbounded on long
  // videos.
  const recent = events.slice(-10).reverse();

  return (
    <div className="ocr-trace">
      <p className="ocr-trace-title">
        <span className="ocr-trace-pulse" aria-hidden="true" />
        Scanning frames for subtitles…
      </p>

      <div className="ocr-trace-body">
        <ul className="ocr-trace-list">
          {recent.map((event, index) => (
            <li
              key={index}
              className={`ocr-trace-item ${event.textFound ? "is-found" : "is-empty"}`}
            >
              <span className="ocr-trace-dot" aria-hidden="true" />
              <span className="ocr-trace-time">{formatTime(event.timestamp)}</span>
              {event.textFound ? (
                <span className="ocr-trace-found">“{event.textFound}”</span>
              ) : (
                <span className="ocr-trace-empty">no subtitle text</span>
              )}
            </li>
          ))}
        </ul>

        {currentFrame && (
          <div className="ocr-trace-current">
            <div className="ocr-trace-frame">
              <img
                src={`data:image/jpeg;base64,${currentFrame.thumbnail}`}
                alt={`Video frame at ${formatTime(currentFrame.timestamp)}`}
              />
              <span className="ocr-trace-scanline" aria-hidden="true" />
            </div>
            <span className="ocr-trace-current-time">
              checking {formatTime(currentFrame.timestamp)}…
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
