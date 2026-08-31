interface TranscriptProps {
  transcript: string;
}

export default function Transcript({
  transcript,
}: TranscriptProps) {
  if (!transcript) {
    return null;
  }

  const copyTranscript = async () => {
    await navigator.clipboard.writeText(transcript);
  };

  return (
    <div className="transcript-container">
      <div className="transcript-header">
        <h2>Transcript</h2>

        <button onClick={copyTranscript}>
          Copy
        </button>
      </div>

      <div className="transcript">
        {transcript}
      </div>
    </div>
  );
}