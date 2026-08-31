import { formatTime } from "../utils/format";

interface ProgressProps {
  status: string;
  currentTime: number;
  totalDuration: number;
  loading: boolean;
  elapsed: number;
}

export default function Progress({
  status,
  currentTime,
  totalDuration,
  loading,
  elapsed,
}: ProgressProps) {

  const progress =
    totalDuration > 0
      ? (currentTime / totalDuration) * 100
      : 0;

  // Before we know the video's duration (downloading, solving YouTube's
  // JS challenge, waking a cold-started server) there's nothing real to
  // show a percentage of. An indeterminate bar + elapsed timer keeps it
  // visible that the app is still working rather than stuck.
  const indeterminate = loading && totalDuration === 0;

  return (
    <div className="progress">

      <p>
        {status}
        {loading && ` (${elapsed}s elapsed)`}
      </p>

      <div className="progress-bar-container">
        <div
          className={
            indeterminate ? "progress-bar progress-bar-indeterminate" : "progress-bar"
          }
          style={indeterminate ? undefined : { width: `${Math.min(progress, 100)}%` }}
        />
      </div>

      {!indeterminate && (
        <p>
          {formatTime(currentTime)} /{" "}
          {formatTime(totalDuration)}
        </p>
      )}

    </div>
  );
}
