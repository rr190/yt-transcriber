interface ProgressProps {
  status: string;
  currentTime: number;
  totalDuration: number;
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0:00";
  }

  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);

  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export default function Progress({
  status,
  currentTime,
  totalDuration,
}: ProgressProps) {

  const progress =
    totalDuration > 0
      ? (currentTime / totalDuration) * 100
      : 0;

  return (
    <div className="progress">

      <p>{status}</p>

      <div className="progress-bar-container">
        <div
          className="progress-bar"
          style={{
            width: `${Math.min(progress, 100)}%`,
          }}
        />
      </div>

      <p>
        {formatTime(currentTime)} /{" "}
        {formatTime(totalDuration)}
      </p>

    </div>
  );
}